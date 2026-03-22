"""
payments/yoo_client.py
======================
Production-ready client for the Yo! Payments Business API (Uganda).

Protocol  : HTTP POST
Headers   : Content-Type: text/xml
            Content-transfer-encoding: text
Auth      : APIUsername + APIPassword embedded in every XML <Request>
Endpoints : paymentsapi1.yo.co.ug  (primary)
            paymentsapi2.yo.co.ug  (fallback, auto-used on failure)

Credentials (resolved in order):
  1. Constructor arguments
  2. Environment variables:
       YO_API_USERNAME
       YO_API_PASSWORD
       YO_API_PRIMARY_URL   (optional override)
       YO_API_BACKUP_URL    (optional override)

NEVER call this client from the frontend.
All requests must originate from this Django backend only.

IPN (Instant Payment Notification)
------------------------------------
Pass notification_url / failure_url to deposit_funds() or withdraw_funds().
Yo! will POST the result XML to those URLs when the transaction settles.
→ Handled by yoo_ipn() in payments/ipn_views.py
"""

import logging
import os
import xml.etree.ElementTree as ET

import requests

from payments.exceptions import YoNetworkError, YoPaymentsError, YoValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults (overridable via env)
# ---------------------------------------------------------------------------

_DEFAULT_PRIMARY = "https://paymentsapi1.yo.co.ug/ybs/task.php"
_DEFAULT_BACKUP  = "https://paymentsapi2.yo.co.ug/ybs/task.php"
_TIMEOUT         = 60  # seconds per endpoint

# Terminal-success TransactionStatus values
_SUCCESS_STATUSES = frozenset({"SUCCEEDED", "SUCCESS", "SUCCESSFUL", "COMPLETED", "APPROVED"})

# Terminal-failure TransactionStatus values
_FAILED_STATUSES = frozenset({"FAILED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED", "INDETERMINATE"})

# Yo! narrative max length (truncated silently if exceeded)
_NARRATIVE_MAX = 100


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class YoPaymentsClient:
    """
    Django-friendly client for the Yo! Payments Business API.

    Usage::

        client = YoPaymentsClient()

        result = client.deposit_funds(
            amount=5000,
            account="256771234567",
            reference="ORDER-abc123",
            narrative="Internet voucher",
            notification_url="https://spotpay.it.com/payments/webhook/yoo/ipn/",
            failure_url="https://spotpay.it.com/payments/webhook/yoo/failure/",
        )

        if YoPaymentsClient.is_pending(result):
            # USSD prompt sent — wait for IPN or poll check_transaction_status()
            pass
        elif YoPaymentsClient.is_success(result):
            ref = result["transaction_reference"]
        elif YoPaymentsClient.is_error(result):
            raise Exception(result["error_message"])
    """

    def __init__(self, username: str = None, password: str = None):
        self.username = (username or os.environ.get("YO_API_USERNAME", "")).strip()
        self.password = (password or os.environ.get("YO_API_PASSWORD", "")).strip()

        if not self.username or not self.password:
            raise YoPaymentsError(
                "YO_API_USERNAME and YO_API_PASSWORD must be set."
            )

        self._endpoints = [
            os.environ.get("YO_API_PRIMARY_URL", _DEFAULT_PRIMARY).strip(),
            os.environ.get("YO_API_BACKUP_URL",  _DEFAULT_BACKUP).strip(),
        ]

    # -----------------------------------------------------------------------
    # A. deposit_funds — pull money from customer (USSD push)
    # -----------------------------------------------------------------------

    def deposit_funds(
        self,
        amount: int,
        account: str,
        reference: str,
        narrative: str = "Payment",
        notification_url: str = None,
        failure_url: str = None,
        provider_code: str = None,
        non_blocking: str = "TRUE",
        provider_reference_text: str = None,
        narrative_filename: str = None,
        narrative_file_base64: str = None,
        auth_signature_base64: str = None,
    ) -> dict:
        """
        Pull money from a mobile money account (USSD push to customer).

        With NonBlocking=TRUE (default) Yo! returns immediately with
        TransactionStatus=PENDING. The final result arrives via IPN
        (InstantNotificationUrl / FailureNotificationUrl).

        Args:
            amount                : Amount in UGX (integer, no decimals).
            account               : Customer phone in international format
                                    without '+', e.g. "256771234567".
            reference             : Your unique internal reference (UUID recommended).
            narrative             : Description shown on customer's phone (max 100 chars).
            notification_url      : IPN URL Yo! POSTs to on SUCCESS.
                                    → handle in ipn_views.yoo_ipn()
            failure_url           : IPN URL Yo! POSTs to on FAILURE.
                                    → handle in ipn_views.yoo_failure_notification()
            provider_code         : "MTN" or "AIRTEL" — optional, Yo! auto-detects.
            non_blocking          : "TRUE" (default) returns immediately.
                                    "FALSE" waits synchronously (not recommended).
            provider_reference_text : Text shown on customer's MNO statement.
            narrative_filename    : Filename for narrative attachment (optional).
            narrative_file_base64 : Base64-encoded narrative file (optional).
            auth_signature_base64 : AuthenticationSignatureBase64 (optional).

        Returns:
            Normalized response dict. Use is_pending() / is_success() / is_error().
        """
        self._validate_phone(account)

        fields = {
            "Method":            "acdepositfunds",
            "NonBlocking":       non_blocking,
            "Amount":            str(int(amount)),
            "Account":           self._normalize_phone(account),
            "Narrative":         self._truncate(narrative, _NARRATIVE_MAX),
            "ExternalReference": str(reference),
        }
        if provider_code:
            fields["AccountProviderCode"] = provider_code
        if provider_reference_text:
            fields["ProviderReferenceText"] = provider_reference_text
        if notification_url:
            # Yo! POSTs result XML here when transaction completes (success)
            fields["InstantNotificationUrl"] = notification_url
        if failure_url:
            # Yo! POSTs result XML here when transaction fails
            fields["FailureNotificationUrl"] = failure_url
        if narrative_filename:
            fields["NarrativeFileName"] = narrative_filename
        if narrative_file_base64:
            fields["NarrativeFileBase64"] = narrative_file_base64
        if auth_signature_base64:
            fields["AuthenticationSignatureBase64"] = auth_signature_base64

        return self._post_xml(self._build_xml_request(fields))

    # -----------------------------------------------------------------------
    # B. withdraw_funds — push money to recipient (disbursement)
    # -----------------------------------------------------------------------

    def withdraw_funds(
        self,
        amount: int,
        account: str,
        reference: str,
        narrative: str = "Withdrawal",
        provider_code: str = None,
        non_blocking: str = "TRUE",
        provider_reference_text: str = None,
        transaction_limit_account_identifier: str = None,
        narrative_filename: str = None,
        narrative_file_base64: str = None,
        public_key_nonce: str = None,
        public_key_signature_base64: str = None,
    ) -> dict:
        """
        Push money to a mobile money account (payout / disbursement).

        Note on public key authentication:
            public_key_nonce and public_key_signature_base64 are optional
            UNLESS public key authentication is enabled on your Yo! account,
            in which case both become mandatory.

        Args:
            amount                              : Amount in UGX (integer).
            account                             : Recipient phone, e.g. "256771234567".
            reference                           : Your unique internal reference.
            narrative                           : Description (max 100 chars).
            provider_code                       : "MTN" or "AIRTEL" (optional).
            non_blocking                        : "TRUE" or "FALSE".
            provider_reference_text             : Text on recipient's MNO statement.
            transaction_limit_account_identifier: TransactionLimitAccountIdentifier (optional).
            narrative_filename                  : Filename for narrative attachment (optional).
            narrative_file_base64               : Base64-encoded narrative file (optional).
            public_key_nonce                    : PublicKeyAuthenticationNonce.
                                                  Required if public key auth is enabled.
            public_key_signature_base64         : PublicKeyAuthenticationSignatureBase64.
                                                  Required if public key auth is enabled.

        Returns:
            Normalized response dict.
        """
        self._validate_phone(account)

        fields = {
            "Method":            "acwithdrawfunds",
            "NonBlocking":       non_blocking,
            "Amount":            str(int(amount)),
            "Account":           self._normalize_phone(account),
            "Narrative":         self._truncate(narrative, _NARRATIVE_MAX),
            "InternalReference": str(reference),
            "ExternalReference": str(reference),
        }
        if provider_code:
            fields["AccountProviderCode"] = provider_code
        if provider_reference_text:
            fields["ProviderReferenceText"] = provider_reference_text
        if transaction_limit_account_identifier:
            fields["TransactionLimitAccountIdentifier"] = transaction_limit_account_identifier
        if narrative_filename:
            fields["NarrativeFileName"] = narrative_filename
        if narrative_file_base64:
            fields["NarrativeFileBase64"] = narrative_file_base64
        if public_key_nonce:
            fields["PublicKeyAuthenticationNonce"] = public_key_nonce
        if public_key_signature_base64:
            fields["PublicKeyAuthenticationSignatureBase64"] = public_key_signature_base64

        return self._post_xml(self._build_xml_request(fields))

    # -----------------------------------------------------------------------
    # C. check_balance
    # -----------------------------------------------------------------------

    def check_balance(self) -> dict:
        """
        Check the Yo! business account balance.

        Returns:
            Normalized response dict. On success, 'balance' key contains the amount.
        """
        return self._post_xml(self._build_xml_request({"Method": "acacctbalance"}))

    # -----------------------------------------------------------------------
    # D. check_transaction_status
    # -----------------------------------------------------------------------

    def check_transaction_status(self, reference: str) -> dict:
        """
        Poll the status of a previously initiated transaction.

        Use this to confirm PENDING transactions when IPN is not received.

        Args:
            reference : The ExternalReference / InternalReference used when
                        initiating the transaction.

        Returns:
            Normalized response dict with 'transaction_status' and
            'transaction_reference' keys.
        """
        return self._post_xml(self._build_xml_request({
            "Method":                    "actransactioncheckstatus",
            "PrivateTransactionReference": str(reference),
        }))

    # -----------------------------------------------------------------------
    # E. verify_account_validity
    # -----------------------------------------------------------------------

    def verify_account_validity(self, account: str, provider_code: str = None) -> dict:
        """
        Verify that a mobile money account exists and is active.

        Args:
            account       : Phone number, e.g. "256771234567".
            provider_code : "MTN" or "AIRTEL" (optional).

        Returns:
            Normalized response dict.
        """
        self._validate_phone(account)

        fields = {
            "Method":  "acverifyaccountvalidity",
            "Account": self._normalize_phone(account),
        }
        if provider_code:
            fields["AccountProviderCode"] = provider_code

        return self._post_xml(self._build_xml_request(fields))

    # -----------------------------------------------------------------------
    # Response classification helpers (static — usable without an instance)
    # -----------------------------------------------------------------------

    @staticmethod
    def is_success(response: dict) -> bool:
        """
        True when Status=OK + StatusCode=0,
        OR TransactionStatus is a known terminal-success value.
        """
        ok_zero = (
            str(response.get("status", "")).upper() == "OK"
            and str(response.get("status_code", "")) == "0"
        )
        txn = str(response.get("transaction_status", "")).upper()
        return ok_zero or txn in _SUCCESS_STATUSES

    @staticmethod
    def is_pending(response: dict) -> bool:
        """
        True when Status=OK + StatusCode=1,
        OR TransactionStatus=PENDING.
        """
        ok_one = (
            str(response.get("status", "")).upper() == "OK"
            and str(response.get("status_code", "")) == "1"
        )
        txn = str(response.get("transaction_status", "")).upper()
        return ok_one or txn == "PENDING"

    @staticmethod
    def is_error(response: dict) -> bool:
        """
        True when Status=ERROR,
        OR TransactionStatus is a known terminal-failure value.
        """
        if str(response.get("status", "")).upper() == "ERROR":
            return True
        txn = str(response.get("transaction_status", "")).upper()
        return txn in _FAILED_STATUSES

    # -----------------------------------------------------------------------
    # Internal: XML builder
    # -----------------------------------------------------------------------

    def _build_xml_request(self, fields: dict) -> str:
        """
        Build the Yo! API XML payload safely using ElementTree.
        Credentials are injected here — never in user-supplied fields.
        Never uses string concatenation for any value.

        Structure::

            <?xml version="1.0" encoding="UTF-8"?>
            <AutoCreate>
              <Request>
                <APIUsername>...</APIUsername>
                <APIPassword>...</APIPassword>
                <Method>...</Method>
                <!-- other fields -->
              </Request>
            </AutoCreate>
        """
        root = ET.Element("AutoCreate")
        req  = ET.SubElement(root, "Request")

        ET.SubElement(req, "APIUsername").text = self.username
        ET.SubElement(req, "APIPassword").text = self.password

        for key, value in fields.items():
            ET.SubElement(req, key).text = str(value)

        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            + ET.tostring(root, encoding="unicode")
        )

    # -----------------------------------------------------------------------
    # Internal: HTTP POST with endpoint fallback
    # -----------------------------------------------------------------------

    def _post_xml(self, xml_payload: str) -> dict:
        """
        POST xml_payload to Yo! endpoints with automatic fallback.

        Tries primary endpoint first; on timeout or connection error
        falls through to the backup endpoint.

        Headers sent:
            Content-Type: text/xml
            Content-transfer-encoding: text

        Returns:
            Parsed response dict (from _parse_xml_response).

        Raises:
            YoNetworkError: if ALL endpoints fail.
        """
        headers = {
            "Content-Type":              "text/xml",
            "Content-transfer-encoding": "text",
        }
        last_error = None

        for endpoint in self._endpoints:
            try:
                logger.warning("YOO RAW XML SENT: %s", xml_payload)
                logger.info("YOO → %s", endpoint)
                resp = requests.post(
                    endpoint,
                    data=xml_payload.encode("utf-8"),
                    headers=headers,
                    timeout=_TIMEOUT,
                )
                logger.info("YOO ← HTTP %s | %.600s", resp.status_code, resp.text)

                if resp.status_code == 200:
                    result = self._parse_xml_response(resp.text)
                    result["_endpoint"] = endpoint   # metadata: which endpoint responded
                    return result

                last_error = f"HTTP {resp.status_code} from {endpoint}"

            except requests.Timeout:
                last_error = f"Timeout on {endpoint}"
                logger.warning("YOO TIMEOUT: %s — trying next endpoint", endpoint)

            except requests.ConnectionError:
                last_error = f"Connection error on {endpoint}"
                logger.warning("YOO CONNECTION ERROR: %s — trying next endpoint", endpoint)

            except Exception as exc:
                last_error = str(exc)
                logger.exception("YOO UNEXPECTED ERROR on %s: %s", endpoint, exc)

        raise YoNetworkError(f"All Yo! endpoints failed. Last error: {last_error}")

    # -----------------------------------------------------------------------
    # Internal: XML response parser
    # -----------------------------------------------------------------------

    def _parse_xml_response(self, xml_text: str) -> dict:
        """
        Parse Yo! XML response into a normalized Python dict.

        Handles all 3 response types:
          - Success : Status=OK, StatusCode=0
          - Pending : Status=OK, StatusCode=1, TransactionStatus=PENDING
          - Error   : Status=ERROR

        Normalized keys returned:
            status                — "OK" or "ERROR"
            status_code           — "0" (success), "1" (pending), other (error)
            status_message        — human-readable status
            transaction_status    — "SUCCEEDED", "PENDING", "FAILED", etc.
            transaction_reference — Yo! transaction reference
            mno_reference         — MNO (MTN/Airtel) transaction reference
            error_message         — error description (on ERROR responses)
            error_code            — ErrorMessageCode
            balance               — account balance (check_balance only)
            raw                   — original XML string (for debugging/audit)
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.error("YOO XML parse error: %s | raw: %.400s", exc, xml_text)
            return {
                "status":        "ERROR",
                "error_message": f"Invalid XML response: {exc}",
                "raw":           xml_text,
            }

        def _get(tag: str):
            el = root.find(f".//{tag}")
            return el.text.strip() if (el is not None and el.text) else None

        return {
            "status":                _get("Status"),
            "status_code":           _get("StatusCode"),
            "status_message":        _get("StatusMessage"),
            "transaction_status":    _get("TransactionStatus"),
            "transaction_reference": _get("TransactionReference"),
            "mno_reference":         _get("MNOTransactionReferenceId"),
            "error_message":         _get("ErrorMessage"),
            "error_code":            _get("ErrorMessageCode"),
            "balance":               _get("Balance"),
            "raw":                   xml_text,
        }

    # -----------------------------------------------------------------------
    # Internal: input helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """
        Normalize phone to 256XXXXXXXXX format (no '+', no leading 0).
        Yo! requires international format without the '+' prefix.
        """
        phone = str(phone).strip().replace(" ", "").replace("-", "")
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "256" + phone[1:]
        if not phone.startswith("256"):
            phone = "256" + phone
        return phone

    @staticmethod
    def _validate_phone(phone: str) -> None:
        """Raise YoValidationError if phone is clearly invalid."""
        cleaned = str(phone).strip().replace(" ", "").replace("-", "").lstrip("+")
        if not cleaned.isdigit() or len(cleaned) < 9:
            raise YoValidationError(f"Invalid phone number: {phone!r}")

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Silently truncate text to max_len characters."""
        return str(text)[:max_len]

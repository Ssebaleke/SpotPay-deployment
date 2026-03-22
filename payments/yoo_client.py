"""
payments/yoo_client.py
======================
Production-ready client for the Yo! Payments Business API (Uganda).

Protocol  : HTTP POST, Content-Type: text/xml
Auth      : APIUsername + APIPassword embedded in every XML request
Endpoints : paymentsapi1.yo.co.ug  (primary)
            paymentsapi2.yo.co.ug  (fallback)

Credentials are read from environment variables:
    YO_API_USERNAME
    YO_API_PASSWORD

Never call this client from the frontend. All requests must originate
from this Django backend.

IPN (Instant Payment Notification)
-----------------------------------
Pass `notification_url` to deposit_funds / withdraw_funds.
Yo! will POST the result XML to that URL when the transaction completes.
Handle it in payments/views.py → yoo_payment_callback().
"""

import logging
import os
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENDPOINTS = [
    "https://paymentsapi1.yo.co.ug/ybs/task.php",
    "https://paymentsapi2.yo.co.ug/ybs/task.php",
]

_TIMEOUT = 60  # seconds per endpoint attempt

# TransactionStatus values Yo! considers terminal-success
_SUCCESS_STATUSES = {"SUCCEEDED", "SUCCESS", "SUCCESSFUL", "COMPLETED", "APPROVED"}

# TransactionStatus values Yo! considers terminal-failure
_FAILED_STATUSES = {"FAILED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED"}


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class YoPaymentsError(Exception):
    """Raised when the Yo! API returns an ERROR status or all endpoints fail."""

    def __init__(self, message, code=None, raw=None):
        super().__init__(message)
        self.code = code    # ErrorMessageCode from Yo response
        self.raw = raw      # raw XML string for debugging


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

class YoPaymentsClient:
    """
    Django-friendly client for the Yo! Payments Business API.

    Credentials are resolved in this order:
      1. Constructor arguments (username, password)
      2. Environment variables YO_API_USERNAME / YO_API_PASSWORD

    Example::

        client = YoPaymentsClient()
        result = client.deposit_funds(
            amount=5000,
            account="256771234567",
            reference="ORDER-001",
            narrative="Internet voucher",
            notification_url="https://yoursite.com/payments/webhook/yoo/",
        )
        if YoPaymentsClient.is_success(result):
            print("USSD push sent, transaction reference:", result["transaction_reference"])
    """

    def __init__(self, username: str = None, password: str = None):
        self.username = username or os.environ.get("YO_API_USERNAME", "").strip()
        self.password = password or os.environ.get("YO_API_PASSWORD", "").strip()

        if not self.username or not self.password:
            raise YoPaymentsError(
                "YO_API_USERNAME and YO_API_PASSWORD must be set in environment variables."
            )

    # -----------------------------------------------------------------------
    # Public API methods
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

        Args:
            amount              : Amount in UGX (integer).
            account             : Customer phone, e.g. "256771234567".
            reference           : Your unique internal reference (UUID recommended).
            narrative           : Description shown to the customer on their phone.
            notification_url    : IPN URL Yo! POSTs to on success.
                                  → handled by yoo_payment_callback() in views.py
            failure_url         : IPN URL Yo! POSTs to on failure.
            provider_code       : "MTN" or "AIRTEL" (optional, auto-detected by Yo!).
            non_blocking        : "TRUE" returns immediately; "FALSE" waits for completion.
            provider_reference_text : Text shown on customer's MNO statement.
            narrative_filename  : Filename for narrative attachment (optional).
            narrative_file_base64: Base64-encoded narrative file content (optional).
            auth_signature_base64: AuthenticationSignatureBase64 (optional).

        Returns:
            Parsed response dict. Check with is_success() / is_pending() / is_error().
        """
        params = {
            "Method": "acdepositfunds",
            "NonBlocking": non_blocking,
            "Amount": str(int(amount)),
            "Account": self._normalize_phone(account),
            "Narrative": narrative,
            "InternalReference": str(reference),
            "ExternalReference": str(reference),
        }
        if provider_code:
            params["AccountProviderCode"] = provider_code
        if provider_reference_text:
            params["ProviderReferenceText"] = provider_reference_text
        if notification_url:
            # IPN: Yo! will POST result XML to this URL on transaction completion
            params["InstantNotificationUrl"] = notification_url
        if failure_url:
            params["FailureNotificationUrl"] = failure_url
        if narrative_filename:
            params["NarrativeFileName"] = narrative_filename
        if narrative_file_base64:
            params["NarrativeFileBase64"] = narrative_file_base64
        if auth_signature_base64:
            params["AuthenticationSignatureBase64"] = auth_signature_base64

        return self._request(params)

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
        Push money to a mobile money account (disbursement / payout).

        Args:
            amount              : Amount in UGX (integer).
            account             : Recipient phone, e.g. "256771234567".
            reference           : Your unique internal reference.
            narrative           : Description.
            provider_code       : "MTN" or "AIRTEL" (optional).
            non_blocking        : "TRUE" or "FALSE".
            provider_reference_text : Text on recipient's MNO statement.
            transaction_limit_account_identifier : TransactionLimitAccountIdentifier (optional).
            narrative_filename  : Filename for narrative attachment (optional).
            narrative_file_base64: Base64-encoded narrative file content (optional).
            public_key_nonce    : PublicKeyAuthenticationNonce (optional).
            public_key_signature_base64: PublicKeyAuthenticationSignatureBase64 (optional).

        Returns:
            Parsed response dict.
        """
        params = {
            "Method": "acwithdrawfunds",
            "NonBlocking": non_blocking,
            "Amount": str(int(amount)),
            "Account": self._normalize_phone(account),
            "Narrative": narrative,
            "InternalReference": str(reference),
            "ExternalReference": str(reference),
        }
        if provider_code:
            params["AccountProviderCode"] = provider_code
        if provider_reference_text:
            params["ProviderReferenceText"] = provider_reference_text
        if transaction_limit_account_identifier:
            params["TransactionLimitAccountIdentifier"] = transaction_limit_account_identifier
        if narrative_filename:
            params["NarrativeFileName"] = narrative_filename
        if narrative_file_base64:
            params["NarrativeFileBase64"] = narrative_file_base64
        if public_key_nonce:
            params["PublicKeyAuthenticationNonce"] = public_key_nonce
        if public_key_signature_base64:
            params["PublicKeyAuthenticationSignatureBase64"] = public_key_signature_base64

        return self._request(params)

    def check_balance(self) -> dict:
        """
        Check the Yo! business account balance.

        Returns:
            Parsed response dict containing 'balance' key on success.
        """
        return self._request({"Method": "accheckbalance"})

    def check_transaction_status(self, reference: str) -> dict:
        """
        Poll the status of a previously initiated transaction.

        Args:
            reference : The InternalReference used when initiating the transaction.

        Returns:
            Parsed response dict with 'transaction_status' and 'transaction_reference'.
        """
        return self._request({
            "Method": "accheckbalance",
            "InternalReference": str(reference),
        })

    def verify_account_validity(self, account: str, provider_code: str = None) -> dict:
        """
        Verify that a mobile money account exists and is active.

        Args:
            account       : Phone number, e.g. "256771234567".
            provider_code : "MTN" or "AIRTEL" (optional).

        Returns:
            Parsed response dict.
        """
        params = {
            "Method": "acverifyaccountvalidity",
            "Account": self._normalize_phone(account),
        }
        if provider_code:
            params["AccountProviderCode"] = provider_code

        return self._request(params)

    # -----------------------------------------------------------------------
    # Response classification helpers (static — usable without an instance)
    # -----------------------------------------------------------------------

    @staticmethod
    def is_success(response: dict) -> bool:
        """Status=OK and StatusCode=0, or TransactionStatus is a known success value."""
        base = (
            str(response.get("status", "")).upper() == "OK"
            and str(response.get("status_code", "")) == "0"
        )
        txn = str(response.get("transaction_status", "")).upper()
        return base or txn in _SUCCESS_STATUSES

    @staticmethod
    def is_pending(response: dict) -> bool:
        """Status=OK and StatusCode=1, or TransactionStatus=PENDING."""
        base = (
            str(response.get("status", "")).upper() == "OK"
            and str(response.get("status_code", "")) == "1"
        )
        txn = str(response.get("transaction_status", "")).upper()
        return base or txn == "PENDING"

    @staticmethod
    def is_error(response: dict) -> bool:
        """Status=ERROR or TransactionStatus is a known failure value."""
        if str(response.get("status", "")).upper() == "ERROR":
            return True
        txn = str(response.get("transaction_status", "")).upper()
        return txn in _FAILED_STATUSES

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone to 256XXXXXXXXX format required by Yo!."""
        phone = str(phone).strip().replace(" ", "").replace("-", "")
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "256" + phone[1:]
        if not phone.startswith("256"):
            phone = "256" + phone
        return phone

    def _build_xml(self, params: dict) -> str:
        """
        Build the Yo! API XML request body safely using ElementTree.
        Never uses string concatenation for user-supplied values.
        """
        root = ET.Element("AutoCreate")
        req = ET.SubElement(root, "Request")

        ET.SubElement(req, "APIUsername").text = self.username
        ET.SubElement(req, "APIPassword").text = self.password

        for key, value in params.items():
            ET.SubElement(req, key).text = str(value)

        return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(root, encoding="unicode")

    def _parse_xml(self, xml_text: str) -> dict:
        """
        Parse Yo! XML response into a normalized Python dict.

        Normalized keys:
            status, status_code, status_message,
            transaction_status, transaction_reference,
            mno_reference, error_message, error_code, balance, raw
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.error("YOO XML parse error: %s | raw: %.300s", exc, xml_text)
            return {
                "status": "ERROR",
                "error_message": f"Invalid XML response: {exc}",
                "raw": xml_text,
            }

        def _get(tag: str):
            el = root.find(f".//{tag}")
            return el.text.strip() if el is not None and el.text else None

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

    def _request(self, params: dict) -> dict:
        """
        POST the XML request to Yo! endpoints with automatic fallback.
        Tries paymentsapi1 first, then paymentsapi2.

        Raises:
            YoPaymentsError: if all endpoints fail (network/timeout).
        """
        xml_body = self._build_xml(params)
        headers = {"Content-Type": "text/xml; charset=utf-8"}
        last_error = None

        for endpoint in _ENDPOINTS:
            try:
                logger.info("YOO REQUEST: endpoint=%s method=%s", endpoint, params.get("Method"))
                response = requests.post(
                    endpoint,
                    data=xml_body.encode("utf-8"),
                    headers=headers,
                    timeout=_TIMEOUT,
                )
                logger.info(
                    "YOO RESPONSE: endpoint=%s http_status=%s body=%.500s",
                    endpoint, response.status_code, response.text,
                )

                if response.status_code == 200:
                    return self._parse_xml(response.text)

                last_error = f"HTTP {response.status_code} from {endpoint}"

            except requests.Timeout:
                last_error = f"Timeout on {endpoint}"
                logger.warning("YOO TIMEOUT: %s", endpoint)

            except requests.ConnectionError:
                last_error = f"Connection error on {endpoint}"
                logger.warning("YOO CONNECTION ERROR: %s", endpoint)

            except Exception as exc:
                last_error = str(exc)
                logger.exception("YOO UNEXPECTED ERROR: %s", exc)

        raise YoPaymentsError(f"All Yo! endpoints failed. Last error: {last_error}")

"""
Yo! Payments Uganda - Production API Client
Supports: deposit_funds, withdraw_funds, check_balance,
          check_transaction_status, verify_account_validity
Endpoint fallback: paymentsapi1 → paymentsapi2
"""

import logging
import os
import xml.etree.ElementTree as ET

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_ENDPOINTS = [
    "https://paymentsapi1.yo.co.ug/ybs/task.php",
    "https://paymentsapi2.yo.co.ug/ybs/task.php",
]

TIMEOUT = 60


class YoPaymentsError(Exception):
    def __init__(self, message, code=None, raw=None):
        super().__init__(message)
        self.code = code
        self.raw = raw


class YoPaymentsClient:
    """
    Django-friendly client for Yo! Payments Business API.

    Credentials are read from environment variables:
        YO_API_USERNAME
        YO_API_PASSWORD

    Usage:
        client = YoPaymentsClient()
        result = client.deposit_funds(
            amount=5000,
            account="256771234567",
            reference="ORDER-001",
            narrative="Internet voucher payment",
            notification_url="https://yoursite.com/payments/webhook/yoo/",
        )
    """

    def __init__(self):
        self.username = os.environ.get("YO_API_USERNAME") or getattr(settings, "YO_API_USERNAME", "")
        self.password = os.environ.get("YO_API_PASSWORD") or getattr(settings, "YO_API_PASSWORD", "")

        if not self.username or not self.password:
            raise YoPaymentsError("YO_API_USERNAME and YO_API_PASSWORD must be set in environment.")

    # ─────────────────────────────────────────────
    # PUBLIC METHODS
    # ─────────────────────────────────────────────

    def deposit_funds(self, amount, account, reference, narrative="Payment",
                      notification_url=None, failure_url=None,
                      provider_code=None, non_blocking="FALSE",
                      provider_reference_text=None):
        """
        Pull money from a mobile money account (USSD push to customer).

        Args:
            amount (int): Amount in UGX
            account (str): Customer phone e.g. 256771234567
            reference (str): Your internal reference (unique per transaction)
            narrative (str): Description shown to customer
            notification_url (str): IPN URL called on success
            failure_url (str): IPN URL called on failure
            provider_code (str): e.g. "MTN" or "AIRTEL" (optional, auto-detected)
            non_blocking (str): "TRUE" returns immediately, "FALSE" waits
            provider_reference_text (str): Text shown on customer's statement

        Returns:
            dict: Parsed response with keys: status, status_code, transaction_status,
                  transaction_reference, mno_reference, error_message
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
            # IPN: Yo! will POST to this URL on transaction completion
            params["InstantNotificationUrl"] = notification_url
        if failure_url:
            params["FailureNotificationUrl"] = failure_url

        return self._request(params)

    def withdraw_funds(self, amount, account, reference, narrative="Withdrawal",
                       provider_code=None, non_blocking="FALSE",
                       provider_reference_text=None):
        """
        Push money to a mobile money account (disbursement).

        Args:
            amount (int): Amount in UGX
            account (str): Recipient phone e.g. 256771234567
            reference (str): Your internal reference
            narrative (str): Description
            provider_code (str): e.g. "MTN" or "AIRTEL"
            non_blocking (str): "TRUE" or "FALSE"

        Returns:
            dict: Parsed response
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

        return self._request(params)

    def check_balance(self):
        """
        Check the Yo! business account balance.

        Returns:
            dict: Parsed response including Balance field
        """
        return self._request({"Method": "accheckbalance"})

    def check_transaction_status(self, reference):
        """
        Check the status of a previously initiated transaction.

        Args:
            reference (str): The InternalReference used when initiating

        Returns:
            dict: Parsed response with transaction_status and transaction_reference
        """
        return self._request({
            "Method": "acgetbalance",  # Yo uses acgetbalance for status checks
            "InternalReference": str(reference),
        })

    def verify_account_validity(self, account, provider_code=None):
        """
        Verify that a mobile money account exists and is active.

        Args:
            account (str): Phone number e.g. 256771234567
            provider_code (str): e.g. "MTN" or "AIRTEL"

        Returns:
            dict: Parsed response
        """
        params = {
            "Method": "acverifyaccountvalidity",
            "Account": self._normalize_phone(account),
        }
        if provider_code:
            params["AccountProviderCode"] = provider_code

        return self._request(params)

    # ─────────────────────────────────────────────
    # RESPONSE HELPERS
    # ─────────────────────────────────────────────

    @staticmethod
    def is_success(response):
        return response.get("status") == "OK" and str(response.get("status_code")) == "0"

    @staticmethod
    def is_pending(response):
        return response.get("status") == "OK" and str(response.get("status_code")) == "1"

    @staticmethod
    def is_error(response):
        return response.get("status") == "ERROR"

    # ─────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────

    def _normalize_phone(self, phone):
        phone = str(phone).strip()
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "256" + phone[1:]
        if not phone.startswith("256"):
            phone = "256" + phone
        return phone

    def _build_xml(self, params: dict) -> str:
        root = ET.Element("AutoCreate")
        req = ET.SubElement(root, "Request")

        ET.SubElement(req, "APIUsername").text = self.username
        ET.SubElement(req, "APIPassword").text = self.password

        for key, value in params.items():
            ET.SubElement(req, key).text = str(value)

        return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(root, encoding="unicode")

    def _parse_xml(self, xml_text: str) -> dict:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error(f"YOO XML parse error: {e} | raw: {xml_text[:300]}")
            return {"status": "ERROR", "error_message": f"Invalid XML response: {e}", "raw": xml_text}

        def get(tag):
            el = root.find(f".//{tag}")
            return el.text.strip() if el is not None and el.text else None

        return {
            "status": get("Status"),
            "status_code": get("StatusCode"),
            "status_message": get("StatusMessage"),
            "transaction_status": get("TransactionStatus"),
            "transaction_reference": get("TransactionReference"),
            "mno_reference": get("MNOTransactionReferenceId"),
            "error_message": get("ErrorMessage"),
            "error_code": get("ErrorMessageCode"),
            "balance": get("Balance"),
            "raw": xml_text,
        }

    def _request(self, params: dict) -> dict:
        xml_body = self._build_xml(params)
        headers = {"Content-Type": "text/xml; charset=utf-8"}
        last_error = None

        for endpoint in API_ENDPOINTS:
            try:
                logger.warning(f"YOO REQUEST: endpoint={endpoint} method={params.get('Method')}")
                resp = requests.post(endpoint, data=xml_body.encode("utf-8"), headers=headers, timeout=TIMEOUT)
                logger.warning(f"YOO RESPONSE: status={resp.status_code} body={resp.text[:500]}")

                if resp.status_code == 200:
                    return self._parse_xml(resp.text)

                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"

            except requests.Timeout:
                logger.warning(f"YOO TIMEOUT: endpoint={endpoint}")
                last_error = f"Timeout on {endpoint}"
                continue

            except requests.ConnectionError:
                logger.warning(f"YOO CONNECTION ERROR: endpoint={endpoint}")
                last_error = f"Connection error on {endpoint}"
                continue

            except Exception as e:
                logger.error(f"YOO UNEXPECTED ERROR: {e}")
                last_error = str(e)
                continue

        raise YoPaymentsError(f"All YooPay endpoints failed. Last error: {last_error}")

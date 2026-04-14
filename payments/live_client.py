"""
payments/live_client.py
=======================
Client for the LivePay API (Uganda).

Endpoints:
  POST https://livepay.me/api/collect-money  — initiate collection

Auth:
  Header: Authorization: Bearer <api_key>

Webhook:
  POST to callback URL with JSON payload
  Header: livepay-signature: t=TIMESTAMP,v=HMAC_SHA256
"""

import hashlib
import hmac
import logging
import time
import uuid

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://livepay.me/api"
_TIMEOUT = 15


class LivePayClient:

    def __init__(self, public_key: str, secret_key: str):
        # public_key = accountNumber, secret_key = API key (Bearer token)
        self.account_number = (public_key or "").strip()
        self.api_key = (secret_key or "").strip()

        if not self.account_number or not self.api_key:
            raise ValueError("LivePay account_number and api_key must be set.")

    def send(self, amount: int, phone: str, reference: str = None, description: str = "Vendor withdrawal") -> dict:
        """
        Send money to a mobile money user (disbursement).

        Args:
            amount      : Amount in UGX (integer).
            phone       : Recipient phone (any format accepted).
            reference   : Unique reference ID (max 30 chars, no spaces).
            description : Transaction description.

        Returns:
            dict with keys: success, message, reference, internal_reference.
        """
        # Ensure reference has no spaces and is max 30 chars
        ref = (reference or str(uuid.uuid4()).replace("-", ""))[:30].replace(" ", "")

        payload = {
            "accountNumber": self.account_number,
            "phoneNumber": self._normalize_phone(phone),
            "amount": int(amount),
            "currency": "UGX",
            "reference": ref,
            "description": description,
        }

        try:
            logger.warning("LIVEPAY SEND → phone=%s amount=%s ref=%s",
                           payload["phoneNumber"], payload["amount"], ref)

            resp = requests.post(
                f"{_BASE_URL}/send-money",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=_TIMEOUT,
            )

            logger.warning("LIVEPAY SEND ← HTTP %s | %.600s", resp.status_code, resp.text)
            
            if resp.status_code != 200:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("error", f"HTTP {resp.status_code}")
                except:
                    error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
                return {"success": False, "message": error_msg}
            
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("LIVEPAY SEND network error: %s", exc)
            return {"success": False, "message": str(exc)}
        except ValueError:
            return {"success": False, "message": "Invalid JSON response from LivePay"}

        return data

    def check_status(self, reference: str) -> dict:
        """
        Check the status of a transaction via your reference ID.
        
        Args:
            reference: Your unique reference ID (not internal_reference)
        
        Returns:
            dict with transaction status information
        """
        params = {
            "accountNumber": self.account_number,
            "currency": "UGX",
            "reference": reference
        }
        
        try:
            resp = requests.get(
                f"{_BASE_URL}/transaction-status",
                params=params,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=_TIMEOUT,
            )
            logger.warning("LIVEPAY STATUS ← HTTP %s | %.600s", resp.status_code, resp.text)
            
            if resp.status_code != 200:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("error", f"HTTP {resp.status_code}")
                except:
                    error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
                return {"success": False, "message": error_msg}
            
            return resp.json()
        except requests.RequestException as exc:
            logger.error("LIVEPAY STATUS network error: %s", exc)
            return {"success": False, "message": str(exc)}
        except ValueError:
            return {"success": False, "message": "Invalid JSON response from LivePay"}

    def check_status_by_internal_reference(self, internal_reference: str) -> dict:
        """
        Check the status of a transaction via internal_reference.
        Note: This may not be directly supported by the new API.
        We'll need to store the mapping between our reference and internal_reference.
        
        Args:
            internal_reference: LivePay's internal reference ID
        
        Returns:
            dict with transaction status information
        """
        # Since the new API only accepts our reference, we need to find
        # the original reference from our Payment model
        from payments.models import Payment
        
        try:
            payment = Payment.objects.filter(provider_reference=internal_reference).first()
            if not payment:
                return {"success": False, "message": "Payment not found for internal reference"}
            
            # Extract our original reference from the payment UUID
            our_reference = str(payment.uuid).replace("-", "").replace(" ", "")[:30]
            return self.check_status(our_reference)
            
        except Exception as exc:
            logger.error("LIVEPAY STATUS BY INTERNAL REF error: %s", exc)
            return {"success": False, "message": str(exc)}

    def collect(self, amount: int, phone: str, reference: str = None, description: str = "Payment for internet voucher") -> dict:
        """
        Initiate a mobile money collection (USSD push to customer).
        """
        ref = (reference or str(uuid.uuid4()).replace("-", ""))[:30].replace(" ", "")

        payload = {
            "accountNumber": self.account_number,
            "phoneNumber": self._normalize_phone(phone),
            "amount": int(amount),
            "currency": "UGX",
            "reference": ref,
            "description": description,
        }

        try:
            logger.warning("LIVEPAY COLLECT → phone=%s amount=%s ref=%s",
                           payload["phoneNumber"], payload["amount"], ref)

            resp = requests.post(
                f"{_BASE_URL}/collect-money",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=_TIMEOUT,
            )

            logger.warning("LIVEPAY COLLECT ← HTTP %s | %.600s", resp.status_code, resp.text)
            
            if resp.status_code != 200:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("error", f"HTTP {resp.status_code}")
                except:
                    error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
                return {"success": False, "message": error_msg}
            
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("LIVEPAY COLLECT network error: %s", exc)
            return {"success": False, "message": str(exc)}
        except ValueError:
            return {"success": False, "message": "Invalid JSON response from LivePay"}

        return data

    @staticmethod
    def verify_webhook_signature(secret_key: str, signature_header: str, payload: dict, webhook_url: str = "") -> bool:
        """
        Verify the X-Webhook-Signature header.
        Format: t=TIMESTAMP,v=HMAC_SHA256_HEX
        Signed string: webhook_url + timestamp + status + customer_reference + internal_reference
        """
        try:
            parts = {}
            for part in signature_header.split(","):
                k, v = part.split("=", 1)
                parts[k.strip()] = v.strip()

            timestamp = parts.get("t", "")
            received_sig = parts.get("v", "")

            if not timestamp or not received_sig:
                return False

            if abs(time.time() - int(timestamp)) > 300:
                logger.warning("LIVEPAY WEBHOOK: stale timestamp %s", timestamp)
                return False

            string_to_sign = (
                webhook_url
                + timestamp
                + str(payload.get("status", ""))
                + str(payload.get("customer_reference", ""))
                + str(payload.get("internal_reference", ""))
            )

            expected = hmac.new(
                secret_key.encode(),
                string_to_sign.encode(),
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(expected, received_sig)

        except Exception as exc:
            logger.error("LIVEPAY signature verification error: %s", exc)
            return False

    @staticmethod
    def is_success(data: dict) -> bool:
        """Check if the API response indicates success."""
        return data.get("success") is True

    @staticmethod
    def is_failed(data: dict) -> bool:
        """Check if the API response indicates failure."""
        return data.get("success") is False

    @staticmethod
    def detect_network(phone: str) -> str:
        """Detect MTN or AIRTEL from Uganda phone number."""
        phone = str(phone).strip().replace(" ", "").replace("-", "")
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "256" + phone[1:]
        if not phone.startswith("256"):
            phone = "256" + phone

        local = phone[3:]  # strip 256
        mtn_prefixes = ("77", "78", "76", "39", "31")
        airtel_prefixes = ("70", "74", "75", "20", "73")

        for p in mtn_prefixes:
            if local.startswith(p):
                return "MTN"
        for p in airtel_prefixes:
            if local.startswith(p):
                return "AIRTEL"

        return "MTN"  # default fallback

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone number to format accepted by LivePay.
        LivePay accepts any format, but we'll standardize to 256XXXXXXXXX
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
    def get_transaction_status(data: dict) -> str:
        """Extract normalized status string from check_status response.
        
        LivePay status values: Pending, Success, Failed, Cancelled
        """
        status = str(data.get("status", "")).upper()
        # Normalize status values
        if status in ("SUCCESS", "SUCCESSFUL", "COMPLETED"):
            return "SUCCESS"
        elif status in ("FAILED", "FAILURE", "CANCELLED", "CANCELED"):
            return "FAILED"
        elif status in ("PENDING", "PROCESSING", "IN_PROGRESS"):
            return "PENDING"
        return status

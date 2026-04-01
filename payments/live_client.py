"""
payments/live_client.py
=======================
Client for the LivePay API (Uganda).

Endpoints:
  POST https://livepay.me/api/v1/collect-money  — initiate collection
  (status via webhook only — no polling endpoint documented)

Auth:
  Header: Authorization: Bearer <secret_key>
  Body:   apikey: <public_key>

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

_BASE_URL = "https://livepay.me/api/v1"
_TIMEOUT = 15


class LivePayClient:

    def __init__(self, public_key: str, secret_key: str):
        self.public_key = (public_key or "").strip()
        self.secret_key = (secret_key or "").strip()

        if not self.public_key or not self.secret_key:
            raise ValueError("LivePay public_key and secret_key must be set.")

    def send(self, amount: int, phone: str, network: str, pin: str, reference: str = None) -> dict:
        """
        Send money to a mobile money user (disbursement).

        Args:
            amount    : Amount in UGX (integer, min 500).
            phone     : Recipient phone in international format e.g. 256702069536.
            network   : MTN or AIRTEL.
            pin       : Transaction PIN set in LivePay account settings.
            reference : Unique reference ID (auto-generated if not provided).

        Returns:
            dict with keys: status, message, data.
        """
        ref = reference or str(uuid.uuid4()).replace("-", "")

        payload = {
            "apikey": self.public_key,
            "reference": ref,
            "phone_number": self._normalize_phone(phone),
            "amount": int(amount),
            "currency": "UGX",
            "network": network.upper(),
            "pin": pin,
        }

        try:
            logger.warning("LIVEPAY SEND → phone=%s amount=%s network=%s ref=%s",
                           payload["phone_number"], payload["amount"], payload["network"], ref)

            resp = requests.post(
                f"{_BASE_URL}/send-money",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.secret_key}",
                    "Content-Type": "application/json",
                },
                timeout=_TIMEOUT,
            )

            logger.warning("LIVEPAY SEND ← HTTP %s | %.600s", resp.status_code, resp.text)
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("LIVEPAY SEND network error: %s", exc)
            return {"status": "error", "message": str(exc)}
        except ValueError:
            return {"status": "error", "message": "Invalid JSON response from LivePay"}

        return data

    def check_status(self, transaction_id: str) -> dict:
        """
        Check the status of a transaction.

        Args:
            transaction_id : LivePay transaction ID returned from collect().

        Returns:
            dict with transaction details. transaction.status can be:
            Success, Failed, Pending, Processing, Completed, Error
        """
        payload = {
            "apikey": self.public_key,
            "transaction_id": transaction_id,
        }

        try:
            resp = requests.post(
                f"{_BASE_URL}/transaction-status.php",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.secret_key}",
                    "Content-Type": "application/json",
                },
                timeout=_TIMEOUT,
            )
            logger.warning("LIVEPAY STATUS ← HTTP %s | %.600s", resp.status_code, resp.text)
            return resp.json()
        except requests.RequestException as exc:
            logger.error("LIVEPAY STATUS network error: %s", exc)
            return {"status": "error", "message": str(exc)}
        except ValueError:
            return {"status": "error", "message": "Invalid JSON response from LivePay"}

    @staticmethod
    def get_transaction_status(data: dict) -> str:
        """Extract normalised status string from check_status response."""
        txn = data.get("transaction", {})
        return str(txn.get("status", "")).upper()

    def collect(self, amount: int, phone: str, network: str, reference: str = None) -> dict:
        """
        Initiate a mobile money collection (USSD push to customer).

        Args:
            amount    : Amount in UGX (integer, min 500).
            phone     : Customer phone in international format e.g. 256702069536.
            network   : MTN or AIRTEL.
            reference : Unique reference ID (auto-generated if not provided).

        Returns:
            dict with keys: status, message, data (contains transaction_id, reference).
        """
        ref = reference or str(uuid.uuid4()).replace("-", "")

        payload = {
            "apikey": self.public_key,
            "reference": ref,
            "phone_number": self._normalize_phone(phone),
            "amount": int(amount),
            "currency": "UGX",
            "network": network.upper(),
        }

        try:
            logger.warning("LIVEPAY COLLECT → phone=%s amount=%s network=%s ref=%s",
                           payload["phone_number"], payload["amount"], payload["network"], ref)

            resp = requests.post(
                f"{_BASE_URL}/collect-money",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.secret_key}",
                    "Content-Type": "application/json",
                },
                timeout=_TIMEOUT,
            )

            logger.warning("LIVEPAY COLLECT ← HTTP %s | %.600s", resp.status_code, resp.text)
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("LIVEPAY COLLECT network error: %s", exc)
            return {"status": "error", "message": str(exc)}
        except ValueError:
            return {"status": "error", "message": "Invalid JSON response from LivePay"}

        return data

    @staticmethod
    def verify_webhook_signature(secret_key: str, signature_header: str, payload: dict) -> bool:
        """
        Verify the livepay-signature header.
        Format: t=TIMESTAMP,v=HMAC_SHA256_HEX

        Rejects requests older than 5 minutes.
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

            # Reject stale requests (5 minute window)
            if abs(time.time() - int(timestamp)) > 300:
                logger.warning("LIVEPAY WEBHOOK: stale timestamp %s", timestamp)
                return False

            # Build signed string: timestamp + sorted key+value pairs
            signed_data = timestamp
            for key in sorted(payload.keys()):
                signed_data += str(key) + str(payload[key])

            expected = hmac.new(
                secret_key.encode(),
                signed_data.encode(),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected, received_sig)

        except Exception as exc:
            logger.error("LIVEPAY signature verification error: %s", exc)
            return False

    @staticmethod
    def is_success(data: dict) -> bool:
        return str(data.get("status", "")).lower() == "approved"

    @staticmethod
    def is_failed(data: dict) -> bool:
        status = str(data.get("status", "")).lower()
        return status in ("failed", "cancelled")

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
        phone = str(phone).strip().replace(" ", "").replace("-", "")
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "256" + phone[1:]
        if not phone.startswith("256"):
            phone = "256" + phone
        return phone

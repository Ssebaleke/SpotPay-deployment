"""
payments/kwa_client.py
======================
Client for the KwaPay API (Uganda).

Endpoints:
  POST https://pay.kwaug.net/api/v1/deposit/          — initiate deposit
  POST https://pay.kwaug.net/api/v1/transaction/info/ — check status

Auth: primary_api + secondary_api in JSON body.

IPN: KwaPay POSTs JSON to the callback URL when transaction settles.
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://pay.kwaug.net/api/v1"
_TIMEOUT = 60


class KwaPayClient:

    def __init__(self, primary_api: str = None, secondary_api: str = None):
        self.primary_api = (primary_api or os.environ.get("KWA_PRIMARY_API", "")).strip()
        self.secondary_api = (secondary_api or os.environ.get("KWA_SECONDARY_API", "")).strip()

        if not self.primary_api or not self.secondary_api:
            raise ValueError("KWA_PRIMARY_API and KWA_SECONDARY_API must be set.")

    def deposit(self, amount: int, phone: str, callback_url: str) -> dict:
        """
        Initiate a mobile money deposit (USSD push to customer).

        Args:
            amount       : Amount in UGX (integer).
            phone        : Customer phone in international format e.g. 256771234567.
            callback_url : IPN URL KwaPay POSTs result to when transaction settles.

        Returns:
            Normalized dict with keys: error, internal_reference, status, message, network.
        """
        payload = {
            "primary_api": self.primary_api,
            "secondary_api": self.secondary_api,
            "phone_number": self._normalize_phone(phone),
            "amount": int(amount),
            "callback": callback_url,
        }

        try:
            logger.info("KWA DEPOSIT → %s", payload.get("phone_number"))
            resp = requests.post(
                f"{_BASE_URL}/deposit/",
                json=payload,
                timeout=_TIMEOUT,
            )
            logger.info("KWA DEPOSIT ← HTTP %s | %.600s", resp.status_code, resp.text)
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("KWA DEPOSIT network error: %s", exc)
            return {"error": True, "message": str(exc)}
        except ValueError:
            return {"error": True, "message": "Invalid JSON response from KwaPay"}

        return data

    def withdraw(self, amount: int, phone: str, callback_url: str) -> dict:
        """
        Initiate a mobile money withdrawal (disbursement to vendor).

        Args:
            amount       : Amount in UGX (integer).
            phone        : Vendor phone in international format e.g. 256771234567.
            callback_url : IPN URL KwaPay POSTs result to when transaction settles.

        Returns:
            Normalized dict with keys: error, internal_reference, status, message, network.
        """
        payload = {
            "primary_api": self.primary_api,
            "secondary_api": self.secondary_api,
            "phone_number": self._normalize_phone(phone),
            "amount": int(amount),
            "callback": callback_url,
        }

        try:
            logger.info("KWA WITHDRAW → %s", payload.get("phone_number"))
            resp = requests.post(
                f"{_BASE_URL}/withdraw/",
                json=payload,
                timeout=_TIMEOUT,
            )
            logger.info("KWA WITHDRAW ← HTTP %s | %.600s", resp.status_code, resp.text)
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("KWA WITHDRAW network error: %s", exc)
            return {"error": True, "message": str(exc)}
        except ValueError:
            return {"error": True, "message": "Invalid JSON response from KwaPay"}

        return data

    def check_status(self, internal_reference: str) -> dict:
        """
        Check the status of a previously initiated transaction.

        Args:
            internal_reference : The internal_reference returned by deposit().

        Returns:
            Normalized dict with keys: error, internal_reference, status, network, amount.
            status can be: SUCCESSFUL, FAILED, PENDING
        """
        payload = {
            "primary_api": self.primary_api,
            "secondary_api": self.secondary_api,
            "reference": internal_reference,
        }

        try:
            resp = requests.post(
                f"{_BASE_URL}/transaction/info/",
                json=payload,
                timeout=_TIMEOUT,
            )
            logger.info("KWA STATUS ← HTTP %s | %.600s", resp.status_code, resp.text)
            return resp.json()
        except requests.RequestException as exc:
            logger.error("KWA STATUS network error: %s", exc)
            return {"error": True, "message": str(exc)}
        except ValueError:
            return {"error": True, "message": "Invalid JSON response from KwaPay"}

    @staticmethod
    def is_success(data: dict) -> bool:
        return not data.get("error") and str(data.get("status", "")).upper() == "SUCCESSFUL"

    @staticmethod
    def is_pending(data: dict) -> bool:
        return not data.get("error") and str(data.get("status", "")).upper() == "PENDING"

    @staticmethod
    def is_failed(data: dict) -> bool:
        return data.get("error") or str(data.get("status", "")).upper() == "FAILED"

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

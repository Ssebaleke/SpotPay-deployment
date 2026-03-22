import logging
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger(__name__)


class YooAdapter:
    """
    Yo! Payments (YooPay) - Collections
    Endpoint: POST /YoPayments/transaction/SendPaymentRequest
    Auth: Username/Password in request body
    """

    def __init__(self, provider):
        self.provider = provider
        self.base_url = (provider.base_url or "").rstrip("/")
        self.username = (provider.api_key or "").strip()
        self.password = (provider.api_secret or "").strip()

        if not self.base_url:
            raise ValueError("PaymentProvider.base_url is missing")
        if not self.username or not self.password:
            raise ValueError("YooPay requires username (api_key) and password (api_secret).")

    def charge(self, payment, data: dict):
        phone = (data.get("phone") or data.get("phone_number") or "").strip()
        if not phone:
            raise ValueError("Phone number is required")

        amt = data.get("amount", None)
        if amt is None:
            amt = payment.amount
        amount_int = int(Decimal(str(amt)))

        # Normalize phone: YooPay expects 256XXXXXXXXX
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "256" + phone[1:]
        if not phone.startswith("256"):
            phone = "256" + phone

        webhook_url = f"{settings.SITE_URL}/payments/webhook/yoo/"

        payload = {
            "Origin": "API",
            "MessageType": "SENDPAYMENTREQUEST",
            "APIUsername": self.username,
            "APIPassword": self.password,
            "Account": phone,
            "Amount": str(amount_int),
            "Reference": str(payment.uuid),
            "InternalReference": str(payment.uuid),
            "NonBlocking": "FALSE",
            "CallbackURL": webhook_url,
        }

        url = f"{self.base_url}/YoPayments/transaction/SendPaymentRequest"

        logger.warning(f"YOO CHARGE REQUEST: url={url} phone={phone} amount={amount_int}")

        resp = requests.post(
            url,
            data=payload,
            headers={"Accept": "application/json"},
            timeout=30,
        )

        logger.warning(f"YOO CHARGE RESPONSE: status={resp.status_code} body={resp.text}")

        if resp.status_code >= 400:
            raise ValueError(f"YooPay {resp.status_code}: {resp.text}")

        res = {}
        try:
            res = resp.json()
        except Exception:
            res = {"raw": resp.text}

        # Extract reference from response
        provider_reference = (
            res.get("TransactionReference")
            or res.get("transaction_reference")
            or res.get("reference")
            or res.get("id")
        )
        if not provider_reference and isinstance(res.get("data"), dict):
            provider_reference = res["data"].get("TransactionReference") or res["data"].get("reference")

        logger.warning(f"YOO provider_reference={provider_reference or '(fallback to uuid)'}")

        return str(provider_reference or payment.uuid)

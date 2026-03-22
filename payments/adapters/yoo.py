import logging
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger(__name__)


class YooAdapter:
    """
    Yo! Payments Uganda API
    Endpoint: https://paymentsapi1.yo.co.ug/ybs/task.php
    Auth: APIUsername + APIPassword in POST body
    """

    API_URL = "https://paymentsapi1.yo.co.ug/ybs/task.php"

    def __init__(self, provider):
        self.username = (provider.api_key or "").strip()
        self.password = (provider.api_secret or "").strip()

        if not self.username or not self.password:
            raise ValueError("YooPay requires APIUsername (api_key) and APIPassword (api_secret).")

    def charge(self, payment, data: dict):
        phone = (data.get("phone") or data.get("phone_number") or "").strip()
        if not phone:
            raise ValueError("Phone number is required")

        amt = data.get("amount") or payment.amount
        amount_int = int(Decimal(str(amt)))

        # Normalize to 256XXXXXXXXX
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "256" + phone[1:]
        if not phone.startswith("256"):
            phone = "256" + phone

        # Detect provider from phone number
        provider = "MTN"
        if phone.startswith("2567") or phone.startswith("25639"):
            provider = "AIRTEL"

        webhook_url = f"{settings.SITE_URL}/payments/webhook/yoo/"

        payload = {
            "APIUsername": self.username,
            "APIPassword": self.password,
            "method": "acdepositfunds",
            "Amount": str(amount_int),
            "Account": phone,
            "Narrative": "Payment for internet voucher",
            "ExternalReference": str(payment.uuid),
            "Provider": provider,
            "CallbackURL": webhook_url,
        }

        logger.warning(f"YOO CHARGE REQUEST: phone={phone} amount={amount_int} provider={provider}")

        resp = requests.post(
            self.API_URL,
            data=payload,
            timeout=60,
        )

        logger.warning(f"YOO CHARGE RESPONSE: status={resp.status_code} body={resp.text[:500]}")

        if resp.status_code >= 400:
            raise ValueError(f"YooPay {resp.status_code}: {resp.text}")

        # Parse response - YooPay returns key=value pairs or JSON
        provider_reference = None
        try:
            res = resp.json()
            provider_reference = (
                res.get("TransactionReference")
                or res.get("transaction_reference")
                or res.get("reference")
            )
        except Exception:
            # Try key=value format
            for line in resp.text.splitlines():
                if "TransactionReference" in line or "transaction_reference" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        provider_reference = parts[1].strip()
                        break

        logger.warning(f"YOO provider_reference={provider_reference or '(fallback to uuid)'}")

        return str(provider_reference or payment.uuid)

import logging
import requests
from requests.auth import HTTPBasicAuth
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger(__name__)


class MomoAdapter:
    """
    MakyPay Wire API - Collections (Mobile Money)
    Endpoint: POST /api/v1/collections/collect-money
    Auth: Basic Auth
    Body: application/x-www-form-urlencoded (use data=...)
    Required fields: phone_number, amount, reference
    """

    def __init__(self, provider):
        self.provider = provider
        self.base_url = (provider.base_url or "").rstrip("/")

        # IMPORTANT: MakyPay is demanding Basic Auth.
        # Put API_USERNAME in api_key and API_PASSWORD in api_secret.
        self.username = (provider.api_key or "").strip()
        self.password = (provider.api_secret or "").strip()

        if not self.base_url:
            raise ValueError("PaymentProvider.base_url is missing")
        if not self.username or not self.password:
            raise ValueError(
                "MakyPay requires Basic Auth. Set api_key=API_USERNAME and api_secret=API_PASSWORD."
            )

    def _safe_json(self, resp):
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    def charge(self, payment, data: dict):
        # accept either key
        phone = (data.get("phone") or data.get("phone_number") or "").strip()
        if not phone:
            raise ValueError("Phone number is required")

        # amount fallback (either from payment or passed in)
        amt = data.get("amount", None)
        if amt is None:
            amt = payment.amount

        amount_int = int(Decimal(str(amt)))
        currency = (data.get("currency") or getattr(payment, "currency", None) or "UGX")

        # Format phone number for MakyPay (must be 256XXXXXXXXX, 12 digits, no +)
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "256" + phone[1:]
        if not phone.startswith("256"):
            phone = "256" + phone   # Fallback, though ideally already mapped

        webhook_url = f"{settings.SITE_URL}/payments/webhook/makypay/"

        payload = {
            "phone_number": phone,
            "amount": str(amount_int),
            "country": "UG",
            "reference": str(payment.uuid),
            "currency": str(currency),
            "callback_url": webhook_url,
            "webhook_url": webhook_url,
        }

        url = f"{self.base_url}/api/v1/collections/collect-money"

        logger.warning(f"MAKYPAY CHARGE REQUEST: url={url} payload={payload}")

        resp = requests.post(
            url,
            auth=HTTPBasicAuth(self.username, self.password),
            data=payload,
            headers={"Accept": "application/json"},
            timeout=30,
        )

        logger.warning(f"MAKYPAY CHARGE RESPONSE: status={resp.status_code} body={resp.text}")

        if resp.status_code >= 400:
            raise ValueError(f"MakyPay {resp.status_code}: {resp.text}")

        res = self._safe_json(resp)

        # Extract provider reference — try top-level then nested data{}
        def _extract_ref(d):
            return (
                d.get("reference")
                or d.get("transaction_id")
                or d.get("transactionId")
                or d.get("uuid")
                or d.get("id")
            )

        provider_reference = _extract_ref(res)
        if not provider_reference and isinstance(res.get("data"), dict):
            provider_reference = _extract_ref(res["data"])

        logger.warning(f"MAKYPAY provider_reference={provider_reference or '(fallback to uuid)'}")

        return str(provider_reference or payment.uuid)

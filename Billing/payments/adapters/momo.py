import requests
from requests.auth import HTTPBasicAuth
from decimal import Decimal


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

        payload = {
            "phone_number": phone,              # required
            "amount": str(amount_int),          # required (send as string in forms)
            "reference": str(payment.uuid),     # required
            "currency": str(currency),          # optional
        }

        url = f"{self.base_url}/api/v1/collections/collect-money"

        print("MAKYPAY URL:", url)
        print("MAKYPAY FORM PAYLOAD:", payload)

        # ✅ use data= (form), NOT json=
        resp = requests.post(
            url,
            auth=HTTPBasicAuth(self.username, self.password),
            data=payload,
            headers={"Accept": "application/json"},
            timeout=30,
        )

        if resp.status_code >= 400:
            raise ValueError(f"MakyPay {resp.status_code} at {resp.url}: {self._safe_json(resp)}")

        res = self._safe_json(resp)

        provider_reference = (
            res.get("reference")
            or res.get("transaction_id")
            or res.get("uuid")
            or res.get("id")
        )

        if not provider_reference and isinstance(res.get("data"), dict):
            d = res["data"]
            provider_reference = (
                d.get("reference")
                or d.get("transaction_id")
                or d.get("uuid")
                or d.get("id")
            )

        # fallback: at least store your own ref
        return str(provider_reference or payment.uuid)

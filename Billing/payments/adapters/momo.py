import requests
from decimal import Decimal


class MomoAdapter:
    def __init__(self, provider):
        self.provider = provider
        self.base_url = (provider.base_url or "").rstrip("/")
        self.public_key = provider.api_key
        self.secret_key = provider.api_secret

        if not self.base_url:
            raise ValueError("PaymentProvider.base_url is missing")
        if not self.public_key:
            raise ValueError("PaymentProvider.api_key (public key) is missing")
        if not self.secret_key:
            raise ValueError("PaymentProvider.api_secret (secret key) is missing")

    def _headers(self):
        # NOTE: If MakyPay expects different header names, we’ll adjust after we see response.
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-PUBLIC-KEY": self.public_key,
            "X-SECRET-KEY": self.secret_key,
        }

    def charge(self, payment, data):
        phone = (data.get("phone") or "").strip()
        if not phone:
            raise ValueError("Phone number is required")

        amount = payment.amount
        amount_int = int(Decimal(str(amount)))

        payload = {
            "phone": phone,
            "amount": amount_int,
            "currency": getattr(payment, "currency", "UGX") or "UGX",
            "external_reference": str(payment.uuid),
        }

        url_a = f"{self.base_url}/api/v1/collections/request-to-pay"
        url_b = f"{self.base_url}/api/v1/collections/request-to-pay/"

        # Debug prints (you’ll see in terminal)
        print("MAKYPAY ENV:", getattr(self.provider, "environment", "UNKNOWN"))
        print("MAKYPAY TRY A:", url_a)
        print("MAKYPAY TRY B:", url_b)
        print("MAKYPAY PAYLOAD:", payload)

        resp = requests.post(url_a, headers=self._headers(), json=payload, timeout=30)

        if resp.status_code == 404:
            resp = requests.post(url_b, headers=self._headers(), json=payload, timeout=30)

        # If still error, raise clean message
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            raise ValueError(
                f"MakyPay {resp.status_code} at {resp.url}: {err}"
            )

        # Parse success response
        try:
            res = resp.json()
        except Exception:
            raise ValueError(f"MakyPay returned non-JSON success: {resp.text}")

        reference = res.get("reference") or res.get("uuid")
        if not reference and isinstance(res.get("data"), dict):
            reference = res["data"].get("reference") or res["data"].get("uuid")

        if not reference:
            raise ValueError(f"MakyPay response missing reference: {res}")

        return reference

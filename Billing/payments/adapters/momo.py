import uuid


class MomoAdapter:
    def __init__(self, provider):
        self.provider = provider
        self.api_key = provider.api_key
        self.api_secret = provider.api_secret
        self.base_url = provider.base_url

    def charge(self, payment, data):
        """
        Trigger a Mobile Money USSD/STK push.
        This is a SIMULATION / PLACEHOLDER.
        """

        phone = data.get("phone")
        amount = payment.amount

        if not phone:
            raise ValueError("Phone number is required for MoMo payment")

        # 🔥 Normally you would call MTN/Airtel API here
        # For now we simulate a provider reference
        provider_reference = f"MOMO-{uuid.uuid4()}"

        # Log/debug (optional)
        print(
            f"[MOMO] Charging {phone} UGX {amount} "
            f"(ref={provider_reference})"
        )

        return provider_reference

import uuid


class CardAdapter:
    def __init__(self, provider):
        self.provider = provider
        self.api_key = provider.api_key
        self.base_url = provider.base_url

    def charge(self, payment, data):
        """
        Trigger a card payment (e.g. Flutterwave, Stripe).
        Placeholder implementation.
        """

        amount = payment.amount
        email = data.get("email", "guest@example.com")

        # 🔥 Normally you'd redirect or create a payment intent
        provider_reference = f"CARD-{uuid.uuid4()}"

        print(
            f"[CARD] Charging {email} UGX {amount} "
            f"(ref={provider_reference})"
        )

        return provider_reference

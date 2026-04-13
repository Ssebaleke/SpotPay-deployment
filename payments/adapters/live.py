"""
payments/adapters/live.py
SpotPay adapter for LivePay.
Credentials stored in PaymentProvider DB record (api_key=public_key, api_secret=secret_key).
"""

import logging
from decimal import Decimal

from payments.live_client import LivePayClient

logger = logging.getLogger(__name__)


class LiveAdapter:
    """SpotPay adapter for LivePay API integration."""

    def __init__(self, provider):
        self.provider = provider
        self.client = LivePayClient(
            public_key=(provider.api_key or "").strip(),
            secret_key=(provider.api_secret or "").strip(),
        )

    def charge(self, payment, data: dict) -> str:
        """
        Initiate a LivePay collection (USSD push to customer).

        Returns:
            internal_reference from LivePay used as provider_reference.

        Raises:
            ValueError: if LivePay returns an error.
        """
        phone = (data.get("phone") or data.get("phone_number") or "").strip()
        if not phone:
            raise ValueError("Phone number is required")

        amount_int = int(Decimal(str(data.get("amount") or payment.amount)))

        # Ensure reference has no spaces and is max 30 chars (LivePay requirement)
        reference = str(payment.uuid).replace("-", "").replace(" ", "")[:30]

        result = self.client.collect(
            amount=amount_int,
            phone=phone,
            reference=reference,
        )

        logger.warning("LIVEPAY ADAPTER RESULT: %s", result)

        if not result.get("success"):
            error_msg = result.get("message") or result.get("error") or "Unknown error"
            raise ValueError(f"LivePay error: {error_msg}")

        # Use internal_reference for webhook matching
        return result.get("internal_reference") or reference

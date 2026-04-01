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
            reference used as provider_reference.

        Raises:
            ValueError: if LivePay returns an error.
        """
        phone = (data.get("phone") or data.get("phone_number") or "").strip()
        if not phone:
            raise ValueError("Phone number is required")

        amount_int = int(Decimal(str(data.get("amount") or payment.amount)))
        network = self.client.detect_network(phone)

        # Use payment UUID as reference for idempotency
        reference = str(payment.uuid).replace("-", "")

        result = self.client.collect(
            amount=amount_int,
            phone=phone,
            network=network,
            reference=reference,
        )

        logger.warning("LIVEPAY ADAPTER RESULT: %s", result)

        if result.get("status") == "error" or result.get("status") not in ("success",):
            raise ValueError(f"LivePay error: {result.get('message', 'Unknown error')}")

        # LivePay returns transaction_id — use our reference as provider_reference
        # since that's what we'll match on webhook
        transaction_id = result.get("data", {}).get("transaction_id") or reference
        return transaction_id

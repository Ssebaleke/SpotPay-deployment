"""
payments/adapters/kwa.py
SpotPay adapter for KwaPay.
Credentials stored in PaymentProvider DB record (api_key=primary_api, api_secret=secondary_api).
"""

import logging
from decimal import Decimal

from django.conf import settings

from payments.kwa_client import KwaPayClient

logger = logging.getLogger(__name__)


class KwaAdapter:

    def __init__(self, provider):
        self.client = KwaPayClient(
            primary_api=(provider.api_key or "").strip(),
            secondary_api=(provider.api_secret or "").strip(),
        )

    def charge(self, payment, data: dict) -> str:
        """
        Initiate a KwaPay deposit (USSD push to customer).

        Returns:
            internal_reference from KwaPay (used as provider_reference).

        Raises:
            ValueError: if KwaPay returns an error.
        """
        phone = (data.get("phone") or data.get("phone_number") or "").strip()
        if not phone:
            raise ValueError("Phone number is required")

        amount_int = int(Decimal(str(data.get("amount") or payment.amount)))
        callback_url = f"{settings.SITE_URL}/payments/webhook/kwa/ipn/"

        result = self.client.deposit(
            amount=amount_int,
            phone=phone,
            callback_url=callback_url,
        )

        logger.warning("KWA ADAPTER RESULT: %s", result)

        if self.client.is_failed(result):
            raise ValueError(f"KwaPay error: {result.get('message', 'Unknown error')}")

        return result.get("internal_reference") or str(payment.uuid)

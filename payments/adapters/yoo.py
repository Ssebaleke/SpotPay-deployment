"""
payments/adapters/yoo.py
SpotPay adapter for Yo! Payments.
Credentials are stored in the PaymentProvider DB record (api_key / api_secret).
"""

import logging
from decimal import Decimal

from django.conf import settings

from payments.yoo_client import YoPaymentsClient
from payments.exceptions import YoPaymentsError

logger = logging.getLogger(__name__)


class YooAdapter:
    """
    Bridges SpotPay's generic payment engine to YoPaymentsClient.

    Credentials come from the active PaymentProvider record:
        api_key    → YO_API_USERNAME
        api_secret → YO_API_PASSWORD
    """

    def __init__(self, provider):
        self.client = YoPaymentsClient(
            username=(provider.api_key or "").strip(),
            password=(provider.api_secret or "").strip(),
        )

    def charge(self, payment, data: dict) -> str:
        """
        Initiate a USSD push (deposit) for the given payment.

        Returns:
            transaction_reference from Yo! (or payment.uuid as fallback).

        Raises:
            ValueError: if Yo! returns an error response.
        """
        phone = (data.get("phone") or data.get("phone_number") or "").strip()
        if not phone:
            raise ValueError("Phone number is required")

        amount_int = int(Decimal(str(data.get("amount") or payment.amount)))

        # Yo! rejects hyphens in InternalReference (error -7)
        # Strip hyphens from UUID to get a clean 32-char alphanumeric reference
        yo_reference = str(payment.uuid).replace("-", "")

        result = self.client.deposit_funds(
            amount=amount_int,
            account=phone,
            reference=yo_reference,
            narrative="Payment for internet voucher",
            notification_url=f"{settings.SITE_URL}/payments/webhook/yoo/ipn/",
            failure_url=f"{settings.SITE_URL}/payments/webhook/yoo/failure/",
            non_blocking="TRUE",
        )

        logger.warning("YOO ADAPTER RESULT: %s", {
            k: v for k, v in result.items() if k != "raw"
        })

        if self.client.is_error(result):
            raise ValueError(
                f"YooPay error: {result.get('error_message') or result.get('status_message')}"
            )

        # Return Yo! transaction_reference if available, else fall back to our UUID
        return result.get("transaction_reference") or str(payment.uuid)

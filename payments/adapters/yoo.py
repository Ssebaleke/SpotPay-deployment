import logging
from django.conf import settings
from payments.yoo_client import YoPaymentsClient, YoPaymentsError

logger = logging.getLogger(__name__)


class YooAdapter:
    """
    SpotPay adapter for Yo! Payments using YoPaymentsClient.
    Credentials come from PaymentProvider.api_key (username) and api_secret (password).
    """

    def __init__(self, provider):
        import os
        os.environ["YO_API_USERNAME"] = (provider.api_key or "").strip()
        os.environ["YO_API_PASSWORD"] = (provider.api_secret or "").strip()
        self.client = YoPaymentsClient()

    def charge(self, payment, data: dict):
        from decimal import Decimal

        phone = (data.get("phone") or data.get("phone_number") or "").strip()
        if not phone:
            raise ValueError("Phone number is required")

        amt = data.get("amount") or payment.amount
        amount_int = int(Decimal(str(amt)))

        notification_url = f"{settings.SITE_URL}/payments/webhook/yoo/"

        result = self.client.deposit_funds(
            amount=amount_int,
            account=phone,
            reference=str(payment.uuid),
            narrative="Payment for internet voucher",
            notification_url=notification_url,
            failure_url=notification_url,
            non_blocking="TRUE",
        )

        logger.warning(f"YOO ADAPTER RESULT: {result}")

        if self.client.is_error(result):
            raise ValueError(f"YooPay error: {result.get('error_message') or result.get('status_message')}")

        return result.get("transaction_reference") or str(payment.uuid)

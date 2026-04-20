"""
payments/adapters/live.py
SpotPay adapter for LivePay.
Credentials stored in PaymentProvider DB record (api_key=public_key, api_secret=secret_key).
"""

import logging
import time
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

        # Retry logic for rate limiting
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            result = self.client.collect(
                amount=amount_int,
                phone=phone,
                reference=reference,
            )

            logger.warning("LIVEPAY ADAPTER RESULT (attempt %d): %s", attempt + 1, result)

            if result.get("success"):
                break
                
            error_msg = result.get("message") or result.get("error") or "Unknown error"
            
            # If rate limited, wait and retry
            if "too many requests" in error_msg.lower() and attempt < max_retries - 1:
                logger.warning("LivePay rate limited, retrying in %d seconds...", retry_delay)
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            
            # Other errors or max retries reached
            raise ValueError(f"LivePay error: {error_msg}")

        # Use internal_reference for webhook matching
        return result.get("internal_reference") or reference

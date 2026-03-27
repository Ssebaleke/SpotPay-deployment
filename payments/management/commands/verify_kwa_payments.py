"""
management/commands/verify_kwa_payments.py
==========================================
Polls KwaPay check_status for all PENDING KwaPay payments
older than 1 minute and completes them if SUCCESSFUL.

Run every 2 minutes via scheduler.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from payments.models import Payment, PaymentProvider
from payments.kwa_client import KwaPayClient
from payments.services.payment_success import handle_payment_success
from sms.services.sms_topup import credit_sms_wallet
from sms.services.notifications import notify_vendor_payment_received, notify_vendor_receipt

logger = logging.getLogger(__name__)


def _handle_subscription_renewal(payment):
    location = payment.location
    now = timezone.now()
    if location.subscription_expires_at and location.subscription_expires_at > now:
        location.subscription_expires_at += timedelta(days=30)
    else:
        location.subscription_expires_at = now + timedelta(days=30)
    location.subscription_active = True
    location.is_active = True
    location.save(update_fields=["subscription_expires_at", "subscription_active", "is_active"])


class Command(BaseCommand):
    help = "Poll KwaPay for PENDING payments and complete them if SUCCESSFUL"

    def handle(self, *args, **options):
        provider = PaymentProvider.objects.filter(provider_type="KWA", is_active=True).first()
        if not provider:
            self.stdout.write("No active KwaPay provider — skipping")
            return

        client = KwaPayClient(
            primary_api=provider.api_key,
            secondary_api=provider.api_secret,
        )

        # Only check payments older than 1 min and younger than 24 hours
        cutoff_min = timezone.now() - timedelta(minutes=1)
        cutoff_max = timezone.now() - timedelta(hours=24)

        pending = Payment.objects.filter(
            status="PENDING",
            provider=provider,
            initiated_at__lte=cutoff_min,
            initiated_at__gte=cutoff_max,
        ).exclude(provider_reference=None)

        self.stdout.write(f"Checking {pending.count()} pending KwaPay payments...")

        for payment in pending:
            try:
                result = client.check_status(payment.provider_reference)
                status = str(result.get("status", "")).upper()
                logger.warning("KWA VERIFY CMD: ref=%s status=%s", payment.provider_reference, status)

                payment_id = None
                run_success_handler = False

                with transaction.atomic():
                    p = Payment.objects.select_for_update().get(pk=payment.pk)

                    if p.status != "PENDING":
                        continue

                    p.raw_callback_data = result

                    if status == "SUCCESSFUL":
                        p.mark_success(result)

                        if p.purpose == "SUBSCRIPTION" and p.location_id:
                            _handle_subscription_renewal(p)

                        if p.purpose == "SMS_PURCHASE" and p.vendor_id:
                            try:
                                credit_sms_wallet(vendor=p.vendor, amount_paid=int(p.amount))
                            except Exception as exc:
                                p.processor_message = f"SMS credit warning: {exc}"
                                p.save(update_fields=["processor_message"])

                        if p.vendor_id:
                            if p.purpose in ("SMS_PURCHASE", "SUBSCRIPTION"):
                                notify_vendor_receipt(p)
                            else:
                                notify_vendor_payment_received(p)

                        payment_id = p.id
                        run_success_handler = True
                        self.stdout.write(f"  ✅ Completed payment {p.uuid}")

                    elif status == "FAILED":
                        p.mark_failed(result)
                        self.stdout.write(f"  ❌ Failed payment {p.uuid}")

                if run_success_handler and payment_id:
                    p = Payment.objects.get(id=payment_id)
                    handle_payment_success(p)

            except Exception as exc:
                logger.error("KWA VERIFY CMD error for %s: %s", payment.provider_reference, exc)

        self.stdout.write("Done.")

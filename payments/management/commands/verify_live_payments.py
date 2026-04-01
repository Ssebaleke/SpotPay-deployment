"""
management/commands/verify_live_payments.py
============================================
Polls LivePay transaction-status for all PENDING LivePay payments
older than 1 minute and completes them if successful.

Run every 2 minutes via scheduler.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from payments.models import Payment, PaymentProvider
from payments.live_client import LivePayClient
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
    help = "Poll LivePay for PENDING payments and complete them if successful"

    def handle(self, *args, **options):
        provider = PaymentProvider.objects.filter(provider_type="LIVE", is_active=True).first()
        if not provider:
            self.stdout.write("No active LivePay provider — skipping")
            return

        client = LivePayClient(
            public_key=provider.api_key,
            secret_key=provider.api_secret,
        )

        cutoff_min = timezone.now() - timedelta(minutes=1)
        cutoff_max = timezone.now() - timedelta(minutes=30)

        pending = Payment.objects.filter(
            status="PENDING",
            provider=provider,
            initiated_at__lte=cutoff_min,
            initiated_at__gte=cutoff_max,
        ).exclude(provider_reference=None)

        # Stale payments older than 30 minutes — check status first
        stale = Payment.objects.filter(
            status="PENDING",
            provider=provider,
            initiated_at__lt=cutoff_max,
        ).exclude(provider_reference=None)

        for payment in stale:
            try:
                result = client.check_status(payment.provider_reference)
                status = LivePayClient.get_transaction_status(result)

                payment_id = None
                run_success_handler = False

                with transaction.atomic():
                    p = Payment.objects.select_for_update().get(pk=payment.pk)
                    if p.status != "PENDING":
                        continue

                    p.raw_callback_data = result

                    if status in ("SUCCESS", "COMPLETED"):
                        # Customer paid — complete normally
                        p.mark_success(result)
                        if p.purpose == "SUBSCRIPTION" and p.location_id:
                            _handle_subscription_renewal(p)
                        if p.purpose == "SMS_PURCHASE" and p.vendor_id:
                            try:
                                credit_sms_wallet(vendor=p.vendor, amount_paid=int(float(p.amount)))
                            except Exception as exc:
                                p.processor_message = f"SMS credit warning: {exc}"
                                p.save(update_fields=["processor_message"])
                        payment_id = p.id
                        run_success_handler = True
                        self.stdout.write(f"  ✅ Stale payment recovered {p.uuid}")

                    elif status == "FAILED":
                        # Customer was never charged — just auto-fail
                        p.mark_failed({"reason": "Payment failed on provider side"})
                        self.stdout.write(f"  ❌ Provider-failed payment {p.uuid}")

                    else:
                        # Still PENDING/PROCESSING after 30 mins — flag for manual review
                        # Do NOT refund automatically — transaction may still be in-flight
                        p.mark_failed({"reason": "Payment not confirmed after 30 minutes"})
                        p.processor_message = "MANUAL REVIEW REQUIRED — timed out while still PENDING on provider. Verify if customer was charged before refunding."
                        p.save(update_fields=["processor_message"])
                        self.stdout.write(f"  ⚠️ Timed-out PENDING payment flagged for manual review {p.uuid}")

                if run_success_handler and payment_id:
                    p = Payment.objects.get(id=payment_id)
                    handle_payment_success(p)

            except Exception as exc:
                logger.error("Stale LivePay payment check error for %s: %s", payment.provider_reference, exc)

        self.stdout.write(f"Checking {pending.count()} pending LivePay payments...")

        for payment in pending:
            try:
                result = client.check_status(payment.provider_reference)
                status = LivePayClient.get_transaction_status(result)
                logger.warning("LIVE VERIFY CMD: ref=%s status=%s", payment.provider_reference, status)

                if not status or status not in ("SUCCESS", "COMPLETED", "FAILED", "PENDING", "PROCESSING"):
                    age_minutes = (timezone.now() - payment.initiated_at).total_seconds() / 60
                    if age_minutes >= 10:
                        with transaction.atomic():
                            p = Payment.objects.select_for_update().get(pk=payment.pk)
                            if p.status == "PENDING":
                                p.mark_failed({"reason": "No status from LivePay after timeout"})
                                self.stdout.write(f"  ⏱ Timed-out payment {p.uuid} (no LivePay status)")
                    continue

                payment_id = None
                run_success_handler = False

                with transaction.atomic():
                    p = Payment.objects.select_for_update().get(pk=payment.pk)

                    if p.status != "PENDING":
                        continue

                    p.raw_callback_data = result

                    if status in ("SUCCESS", "COMPLETED"):
                        p.mark_success(result)

                        if p.purpose == "SUBSCRIPTION" and p.location_id:
                            _handle_subscription_renewal(p)

                        if p.purpose == "SMS_PURCHASE" and p.vendor_id:
                            try:
                                credit_sms_wallet(vendor=p.vendor, amount_paid=int(float(p.amount)))
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
                logger.error("LIVE VERIFY CMD error for %s: %s", payment.provider_reference, exc)

        self.stdout.write("Done.")

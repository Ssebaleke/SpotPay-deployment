"""
management/commands/retry_voucher_sms.py
=========================================
Finds SUCCESS TRANSACTION payments that have a voucher issued
but no successful SMS sent, and retries sending the SMS.
"""

import logging
from django.core.management.base import BaseCommand
from payments.models import Payment, PaymentVoucher
from sms.models import SMSLog
from sms.services.voucher_pay import send_voucher_sms

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Retry sending voucher SMS for payments where SMS failed or was not sent"

    def handle(self, *args, **options):
        # Find payments that have a voucher but no successful SMS log
        payments_with_vouchers = PaymentVoucher.objects.filter(
            payment__status="SUCCESS",
            payment__purpose="TRANSACTION",
        ).select_related(
            "payment", "payment__vendor", "payment__package", "payment__location", "voucher"
        )

        retried = 0
        skipped = 0

        for pv in payments_with_vouchers:
            payment = pv.payment
            voucher = pv.voucher

            if not payment.phone:
                skipped += 1
                continue

            # Check if a successful SMS was already sent for this payment
            already_sent = SMSLog.objects.filter(
                payment=payment,
                status="SENT",
            ).exists()

            if already_sent:
                skipped += 1
                continue

            # Skip if last failure was due to insufficient balance — vendor needs to top up first
            insufficient_balance = SMSLog.objects.filter(
                payment=payment,
                status="FAILED",
                failure_reason="Insufficient SMS balance",
            ).exists()

            if insufficient_balance:
                skipped += 1
                continue

            # Permanently skip after 3 provider send failures
            provider_failures = SMSLog.objects.filter(
                payment=payment,
                status="FAILED",
            ).exclude(
                failure_reason="Insufficient SMS balance",
            ).count()

            if provider_failures >= 3:
                skipped += 1
                continue

            try:
                success, result = send_voucher_sms(
                    vendor=payment.vendor,
                    phone=payment.phone,
                    voucher_code=voucher.code,
                    package_name=payment.package.name if payment.package else "Package",
                    payment=payment,
                    location=payment.location,
                )

                if success:
                    retried += 1
                    self.stdout.write(f"  ✅ SMS sent for payment {payment.uuid} → {payment.phone}")
                else:
                    self.stdout.write(f"  ❌ SMS failed for {payment.uuid}: {result}")

            except Exception as exc:
                logger.error("retry_voucher_sms error for %s: %s", payment.uuid, exc)
                self.stdout.write(f"  ❌ Error {payment.uuid}: {exc}")

        self.stdout.write(f"Done. Retried {retried}, skipped {skipped}.")

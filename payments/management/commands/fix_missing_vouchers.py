"""
management/commands/fix_missing_vouchers.py
============================================
Finds SUCCESS TRANSACTION payments with no voucher issued
and reruns handle_payment_success to issue voucher + send SMS.
"""

import logging
from django.core.management.base import BaseCommand
from payments.models import Payment, PaymentVoucher
from payments.services.payment_success import handle_payment_success

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Issue missing vouchers for successful payments and send SMS"

    def handle(self, *args, **options):
        # Find SUCCESS TRANSACTION payments with no voucher
        payments = Payment.objects.filter(
            status="SUCCESS",
            purpose="TRANSACTION",
        ).exclude(
            id__in=PaymentVoucher.objects.values_list("payment_id", flat=True)
        ).select_related("vendor", "package", "location")

        self.stdout.write(f"Found {payments.count()} payments missing vouchers...")

        fixed = 0
        for payment in payments:
            try:
                handle_payment_success(payment)
                fixed += 1
                self.stdout.write(f"  ✅ Fixed payment {payment.uuid}")
            except Exception as exc:
                logger.error("fix_missing_vouchers error for %s: %s", payment.uuid, exc)
                self.stdout.write(f"  ❌ Failed {payment.uuid}: {exc}")

        self.stdout.write(f"Done. Fixed {fixed} payments.")

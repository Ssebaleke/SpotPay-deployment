from django.db import transaction

from vouchers.services.issue_voucher import issue_voucher
from sms.services.voucher_pay import send_voucher_sms
from payments.models import PaymentVoucher


def handle_payment_success(payment):
    """
    Called AFTER a payment is SUCCESS.
    Issues voucher ONCE, links it to payment, sends SMS.
    """

    # Hotspot client purchase
    if payment.purpose != "TRANSACTION":
        return

    if not payment.vendor_id or not payment.package_id:
        return

    # idempotency: if already issued, do nothing
    if PaymentVoucher.objects.filter(payment=payment).exists():
        return

    vendor = payment.vendor
    phone = payment.phone
    package = payment.package

    with transaction.atomic():
        # double-check inside lock
        if PaymentVoucher.objects.select_for_update().filter(payment=payment).exists():
            return

        voucher = issue_voucher(
            vendor=vendor,
            package=package,
        )

        PaymentVoucher.objects.create(
            payment=payment,
            voucher=voucher
        )

    # send sms outside transaction
    if phone:
        send_voucher_sms(
            vendor=vendor,
            phone=phone,
            voucher_code=voucher.code,
            package_name=package.name,
        )

# payments/services/payment_success.py

from vouchers.services.issue_voucher import issue_voucher
from sms.services.voucher_pay import send_voucher_sms


def handle_payment_success(payment):
    """
    Called immediately AFTER an end-user payment is successful
    """

    # Only handle voucher purchases
    if payment.purpose != "VOUCHER_PURCHASE":
        return

    vendor = payment.vendor
    phone = payment.phone          # end user phone
    package = payment.package

    # 1️⃣ Issue voucher automatically
    voucher = issue_voucher(
        vendor=vendor,
        package=package,
    )

    # 2️⃣ Send voucher to end user via SMS
    send_voucher_sms(
        vendor=vendor,
        phone=phone,
        voucher_code=voucher.code,
        package_name=package.name,
    )


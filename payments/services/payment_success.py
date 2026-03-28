from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP

from vouchers.services.issue_voucher import issue_voucher
from sms.services.voucher_pay import send_voucher_sms
from sms.services.notifications import notify_vendor_receipt
from payments.models import PaymentVoucher, PaymentSplit, PaymentSystemConfig
from wallets.models import VendorWallet


def handle_payment_success(payment):
    """
    Called AFTER a payment is SUCCESS.
    Issues voucher ONCE, links it to payment, sends SMS, records split.
    """

    if payment.purpose != "TRANSACTION":
        return

    if not payment.vendor_id or not payment.package_id:
        return

    if PaymentVoucher.objects.filter(payment=payment).exists():
        return

    vendor = payment.vendor
    phone = payment.phone
    package = payment.package
    location = payment.location

    with transaction.atomic():
        if PaymentVoucher.objects.select_for_update().filter(payment=payment).exists():
            return

        voucher = issue_voucher(vendor=vendor, package=package)
        PaymentVoucher.objects.create(payment=payment, voucher=voucher)

        # ── Calculate SpotPay commission split ──
        if not PaymentSplit.objects.filter(payment=payment).exists():
            config = PaymentSystemConfig.get()
            mode = getattr(location, 'subscription_mode', 'MONTHLY') if location else 'MONTHLY'

            if mode == 'PERCENTAGE':
                pct = config.percentage_mode_percentage
            else:
                pct = config.subscription_mode_percentage

            amount = Decimal(str(payment.amount))

            # Deduct gateway fee first
            gateway_pct = Decimal('0.00')
            if payment.provider_id:
                gateway_pct = Decimal(str(payment.provider.gateway_fee_percentage or 0))
            gateway_fee = (amount * gateway_pct / Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            net_amount = amount - gateway_fee

            # SpotPay commission on net amount
            spotpay_amount = (net_amount * pct / Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            vendor_amount = net_amount - spotpay_amount

            PaymentSplit.objects.create(
                payment=payment,
                subscription_mode=mode,
                gateway_fee_percentage=gateway_pct,
                gateway_fee_amount=gateway_fee,
                spotpay_percentage=pct,
                spotpay_amount=spotpay_amount,
                vendor_amount=vendor_amount,
            )

            # Credit vendor wallet with their share
            VendorWallet.credit(
                vendor=vendor,
                amount=vendor_amount,
                reference=str(payment.uuid)
            )

    if phone:
        send_voucher_sms(
            vendor=vendor,
            phone=phone,
            voucher_code=voucher.code,
            package_name=package.name,
            payment=payment,
            location=location,
        )

    notify_vendor_receipt(payment)

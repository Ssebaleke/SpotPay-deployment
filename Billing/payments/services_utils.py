from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from hotspot.models import HotspotLocation
from vouchers.models import Voucher
from payments.models import Payment


# =====================================================
# SUBSCRIPTION LOGIC
# =====================================================

def activate_monthly_subscription(location: HotspotLocation):
    """
    Activate or extend a monthly subscription by 30 days
    """
    now = timezone.now()

    if location.subscription_expires_at and location.subscription_expires_at > now:
        location.subscription_expires_at += timedelta(days=30)
    else:
        location.subscription_expires_at = now + timedelta(days=30)

    location.subscription_active = True
    location.is_active = True
    location.save()


# =====================================================
# PAYMENT ENTRY POINT (RESERVATION MODE)
# =====================================================

def initiate_payment(*, location, package, phone, source=None):
    """
    1. Reserve ONE UNUSED voucher
    2. Create PENDING payment
    """

    with transaction.atomic():
        voucher = (
            Voucher.objects
            .select_for_update()
            .filter(
                package=package,
                status='UNUSED'
            )
            .first()
        )

        if not voucher:
            raise Exception("No vouchers available for this package")

        # 🔒 Reserve voucher
        voucher.status = 'RESERVED'
        voucher.save()

        # Create payment
        payment = Payment.objects.create(
            payer_type='CLIENT',
            purpose='TRANSACTION',
            vendor=location.vendor,
            location=location,
            amount=package.price,
            status='PENDING',
            voucher=voucher
        )

    # Stub for now (real gateway later)
    print("=== PAYMENT INITIATED ===")
    print(f"Payment UUID: {payment.uuid}")
    print(f"Voucher Reserved: {voucher.code}")

    return {
        "status": "PENDING",
        "payment_uuid": str(payment.uuid)
    }


# =====================================================
# PAYMENT SUCCESS HANDLER
# =====================================================

def payment_success(payment_uuid, callback_data=None):
    """
    Called when payment provider confirms SUCCESS
    """
    payment = Payment.objects.select_related('voucher').get(uuid=payment_uuid)

    if payment.status == 'SUCCESS':
        return

    voucher = payment.voucher

    voucher.status = 'USED'
    voucher.used_at = timezone.now()
    voucher.save()

    payment.mark_success(callback_data)

    print(f"Payment {payment.uuid} SUCCESS → Voucher {voucher.code} USED")


# =====================================================
# PAYMENT FAILURE HANDLER
# =====================================================

def payment_failed(payment_uuid, callback_data=None):
    """
    Called when payment provider confirms FAILURE
    """
    payment = Payment.objects.select_related('voucher').get(uuid=payment_uuid)

    if payment.status == 'FAILED':
        return

    voucher = payment.voucher

    # 🔄 Return voucher to stock
    voucher.status = 'UNUSED'
    voucher.used_at = None
    voucher.save()

    payment.mark_failed(callback_data)

    print(f"Payment {payment.uuid} FAILED → Voucher {voucher.code} RETURNED")


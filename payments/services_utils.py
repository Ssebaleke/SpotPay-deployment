from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from decimal import Decimal

from hotspot.models import HotspotLocation
from packages.models import Package
from payments.models import Payment
from payments.utils import get_active_provider, load_provider_adapter
from payments.services.payment_success import handle_payment_success


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
    location.save(update_fields=["subscription_expires_at", "subscription_active", "is_active"])


# =====================================================
# PAYMENT ENTRY POINT (REAL GATEWAY MODE)
# =====================================================

def initiate_payment(*, location: HotspotLocation, package: Package, phone: str, source=None, mac_address=None, ip_address=None):
    """
    1) Create PENDING Payment
    2) Call MakyPay request-to-pay (STK/USSD prompt)
    3) Save provider_reference
    """

    provider = get_active_provider()
    if not provider:
        raise Exception("No active payment provider configured")

    if not phone:
        raise Exception("Phone is required")

    # Ensure amount is Decimal
    amount = Decimal(str(package.price))

    with transaction.atomic():
        payment = Payment.objects.create(
            payer_type="CLIENT",
            purpose="TRANSACTION",
            vendor=location.vendor,
            location=location,
            package=package,
            phone=phone,
            amount=amount,
            currency="UGX",
            provider=provider,
            status="PENDING",
            mac_address=mac_address,
            ip_address=ip_address,
        )

    adapter = load_provider_adapter(provider)
    reference = adapter.charge(payment, {
        "phone": phone,
        "amount": str(amount),
        "currency": "UGX",
    })

    payment.provider_reference = reference
    payment.save(update_fields=["provider_reference"])

    return {
        "success": True,
        "status": payment.status,
        "payment_uuid": str(payment.uuid),
        "reference": reference,
        "status_url": f"/payments/status/{reference}/",
        "success_url": f"/payments/success/{payment.uuid}/",
        "message": "Please approve the payment on your phone."
    }


# =====================================================
# PAYMENT SUCCESS HANDLER (called after webhook SUCCESS)
# =====================================================

def payment_success_by_reference(provider_reference: str, callback_data=None):
    """
    Called when payment provider confirms SUCCESS (webhook).
    Uses provider_reference (MakyPay reference) to find Payment.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(provider_reference=provider_reference)

        if payment.status == "SUCCESS":
            return payment

        payment.mark_success(callback_data)

    # After commit: issue voucher + link + sms (idempotent)
    handle_payment_success(payment)
    return payment


# =====================================================
# PAYMENT FAILURE HANDLER (called after webhook FAILED)
# =====================================================

def payment_failed_by_reference(provider_reference: str, callback_data=None):
    """
    Called when payment provider confirms FAILURE (webhook).
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(provider_reference=provider_reference)

        if payment.status == "FAILED":
            return payment

        payment.mark_failed(callback_data)

    return payment

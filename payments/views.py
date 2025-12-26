import uuid
from decimal import Decimal

from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Payment, PaymentProvider, LocationBillingProfile
from hotspot.models import HotspotLocation
from packages.models import Package
from vouchers.models import Voucher


# =====================================================
# SUBSCRIPTION PAYMENT (MODE A ONLY)
# =====================================================

@login_required
def initiate_subscription_payment(request, location_id):
    vendor = request.user.vendor

    location = get_object_or_404(
        HotspotLocation,
        id=location_id,
        vendor=vendor
    )

    billing = location.billing

    # ❌ Mode C → no subscription allowed
    if not billing.subscription_required:
        return HttpResponseForbidden(
            "This location uses percentage-only billing (no subscription)."
        )

    # Already active
    if billing.subscription_valid():
        return redirect('vendor_dashboard')

    payment = Payment.objects.create(
        reference=str(uuid.uuid4()),
        payment_type=Payment.SUBSCRIPTION,
        phone_number=request.user.phone_number,
        amount=billing.subscription_fee,
        vendor=vendor,
        location=location,
        provider=PaymentProvider.objects.filter(is_active=True).first(),
    )

    # Mock success for now
    return redirect('subscription_payment_success', payment.reference)


@login_required
def subscription_payment_success(request, reference):
    payment = get_object_or_404(
        Payment,
        reference=reference,
        payment_type=Payment.SUBSCRIPTION
    )

    if payment.status == Payment.STATUS_SUCCESS:
        return redirect('vendor_dashboard')

    payment.status = Payment.STATUS_SUCCESS
    payment.confirmed_at = timezone.now()
    payment.save(update_fields=['status', 'confirmed_at'])

    billing = payment.location.billing
    billing.subscription_expires_at = (
        timezone.now() +
        timezone.timedelta(days=billing.subscription_period_days)
    )
    billing.save(update_fields=['subscription_expires_at'])

    return redirect('vendor_dashboard')


# =====================================================
# CLIENT VOUCHER PAYMENT (MODE A & MODE C)
# =====================================================

@csrf_exempt
def initiate_voucher_payment(request, location_uuid):
    """
    Called by captive portal
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request"}, status=405)

    location = get_object_or_404(
        HotspotLocation,
        uuid=location_uuid,
        is_active=True
    )

    billing = location.billing

    # ❌ Mode A requires active subscription
    if billing.subscription_required and not billing.subscription_valid():
        return JsonResponse(
            {"error": "Subscription inactive"},
            status=403
        )

    package_id = request.POST.get('package_id')
    phone = request.POST.get('phone')

    if not package_id or not phone:
        return JsonResponse({"error": "Missing data"}, status=400)

    package = get_object_or_404(
        Package,
        id=package_id,
        location=location,
        is_active=True
    )

    payment = Payment.objects.create(
        reference=str(uuid.uuid4()),
        payment_type=Payment.VOUCHER,
        phone_number=phone,
        amount=package.price,
        vendor=location.vendor,
        location=location,
        provider=PaymentProvider.objects.filter(is_active=True).first(),
    )

    return JsonResponse({
        "reference": payment.reference,
        "amount": str(payment.amount)
    })


# =====================================================
# PAYMENT CALLBACK (SHARED)
# =====================================================

@csrf_exempt
def payment_callback(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid method"}, status=405)

    reference = request.POST.get('reference')
    status = request.POST.get('status')

    if not reference or not status:
        return JsonResponse({"error": "Invalid payload"}, status=400)

    payment = get_object_or_404(Payment, reference=reference)

    if payment.status == Payment.STATUS_SUCCESS:
        return JsonResponse({"ok": True})

    if status.lower() == 'success':
        payment.status = Payment.STATUS_SUCCESS
        payment.confirmed_at = timezone.now()
        payment.save(update_fields=['status', 'confirmed_at'])

        # Voucher generation ONLY for voucher payments
        if payment.payment_type == Payment.VOUCHER:
            Voucher.objects.create(
                code=Voucher.generate_code(),
                package=payment.package,
                phone_number=payment.phone_number,
                payment=payment
            )

    else:
        payment.status = Payment.STATUS_FAILED
        payment.save(update_fields=['status'])

    return JsonResponse({"ok": True})

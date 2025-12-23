import uuid
from decimal import Decimal

from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Payment, PaymentProvider
from hotspot.models import HotspotLocation


# =====================================================
# INITIATE SUBSCRIPTION PAYMENT (VENDOR)
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

    # Subscription disabled → nothing to pay
    if not billing.subscription_required:
        return HttpResponseForbidden("Subscription not required for this location.")

    payment = Payment.objects.create(
        reference=str(uuid.uuid4()),
        payment_type='SUBSCRIPTION',
        phone_number=request.user.phone_number,
        amount=billing.subscription_fee,
        vendor=vendor,
        location=location,
        provider=PaymentProvider.objects.filter(is_active=True).first(),
    )

    # 🚧 TEMPORARY (mock redirect)
    # Later: redirect to real payment provider checkout URL
    return redirect('subscription_payment_success', payment.reference)


# =====================================================
# MOCK PAYMENT SUCCESS (FOR NOW)
# =====================================================
# This simulates a provider callback

@login_required
def subscription_payment_success(request, reference):
    payment = get_object_or_404(
        Payment,
        reference=reference,
        payment_type='SUBSCRIPTION'
    )

    payment.status = 'success'
    payment.save(update_fields=['status'])

    return redirect('vendor_dashboard')


# =====================================================
# PAYMENT CALLBACK (PROVIDER → SYSTEM)
# =====================================================
# Real providers will hit this endpoint

@csrf_exempt
def payment_callback(request):
    """
    This endpoint will be called by MTN / Airtel / Flutterwave etc
    """
    # For now, assume payload already validated
    reference = request.POST.get('reference')
    status = request.POST.get('status')

    payment = get_object_or_404(Payment, reference=reference)

    if status == 'success':
        payment.status = 'success'
    else:
        payment.status = 'failed'

    payment.save(update_fields=['status'])

    return JsonResponse({"ok": True})

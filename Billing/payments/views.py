from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from .models import (
    Payment,
    PaymentSystemConfig,
    PaymentSplit
)
from .utils import get_active_provider, load_provider_adapter
from .services.payment_success import handle_payment_success

from wallets.models import VendorWallet


# =====================================================
# INITIATE PAYMENT (USER-FACING)
# =====================================================

def initiate_payment(request):
    provider = get_active_provider()
    if not provider:
        return JsonResponse({"error": "No payment provider configured"}, status=400)

    payment = Payment.objects.create(
        payer_type=request.POST.get("payer_type"),
        purpose=request.POST.get("purpose"),
        vendor_id=request.POST.get("vendor_id"),
        location_id=request.POST.get("location_id"),
        amount=Decimal(request.POST.get("amount")),
        provider=provider,
        phone=request.POST.get("phone"),
        package_id=request.POST.get("package_id"),
    )

    adapter = load_provider_adapter(provider)
    ref = adapter.charge(payment, request.POST)

    payment.provider_reference = ref
    payment.save(update_fields=["provider_reference"])

    return JsonResponse({
        "payment_id": str(payment.uuid),
        "reference": ref,
        "redirect_url": f"/payments/success/{payment.uuid}/"
    })


# =====================================================
# PAYMENT CALLBACK (PROVIDER → SERVER ONLY)
# =====================================================

@csrf_exempt
def payment_callback(request):
    ref = request.POST.get("reference")

    try:
        payment = Payment.objects.get(provider_reference=ref)
    except Payment.DoesNotExist:
        return HttpResponse("INVALID PAYMENT", status=404)

    # Prevent duplicate processing
    if payment.status == "SUCCESS":
        return HttpResponse("OK")

    # -------------------------------------------------
    # MARK PAYMENT SUCCESS
    # -------------------------------------------------
    payment.mark_success(request.POST)

    # 🔥 CENTRAL LOGIC (RESERVE VOUCHER, SEND SMS, ETC)
    handle_payment_success(payment)

    # -------------------------------------------------
    # SUBSCRIPTION PAYMENT
    # -------------------------------------------------
    if payment.purpose == "SUBSCRIPTION":
        location = payment.location
        duration_days = 30

        if location.subscription_expires_at and location.subscription_expires_at > timezone.now():
            location.subscription_expires_at += timedelta(days=duration_days)
        else:
            location.subscription_expires_at = timezone.now() + timedelta(days=duration_days)

        location.subscription_active = True
        location.is_active = True
        location.save()

    # -------------------------------------------------
    # END-USER INTERNET PAYMENT (VOUCHER FLOW)
    # -------------------------------------------------
    if payment.purpose == "VOUCHER_PURCHASE":
        system_cfg = PaymentSystemConfig.objects.first()
        base_pct = system_cfg.base_system_percentage
        subscription_pct = payment.vendor.subscription_percentage

        admin_pct = base_pct + subscription_pct
        admin_amount = (payment.amount * admin_pct) / 100
        vendor_amount = payment.amount - admin_amount

        PaymentSplit.objects.create(
            payment=payment,
            base_system_percentage=base_pct,
            subscription_percentage=subscription_pct,
            admin_amount=admin_amount,
            vendor_amount=vendor_amount
        )

        VendorWallet.credit(
            vendor=payment.vendor,
            amount=vendor_amount,
            reference=payment.uuid
        )

    return HttpResponse("OK")


# =====================================================
# PAYMENT SUCCESS (USER → AUTO LOGIN HERE)
# =====================================================

def payment_success_redirect(request, uuid):
    """
    USER-FACING VIEW
    THIS IS WHERE AUTO CONNECTION HAPPENS
    """

    payment = get_object_or_404(Payment, uuid=uuid)

    if payment.status != "SUCCESS":
        return HttpResponse("Payment not completed", status=400)

    if payment.purpose != "VOUCHER_PURCHASE":
        return HttpResponse("OK")

    voucher = payment.voucher
    location = payment.location

    # 🔑 ONE PLACEHOLDER → username = password
    auto_login_url = (
        f"http://{location.hotspot_dns}/login"
        f"?username={voucher.code}"
        f"&password={voucher.code}"
    )

    return redirect(auto_login_url)

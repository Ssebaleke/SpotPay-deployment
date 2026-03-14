from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect, render
from django.contrib import messages
from django.http import JsonResponse

import requests

from payments.views import initiate_payment
from .models import SMSPricing, VendorSMSWallet, SMSProvider


@login_required
def sms_topup(request):
    vendor = request.user.vendor
    pricing = SMSPricing.objects.filter(is_active=True).first()
    wallet, _ = VendorSMSWallet.objects.get_or_create(vendor=vendor)

    if request.method == "POST":
        amount = request.POST.get("amount")
        phone = request.POST.get("phone")

        if not amount or not phone:
            messages.error(request, "Amount and phone number are required.")
            return redirect("sms:sms_topup")

        # Build a mutable POST copy for payment initiation
        post_data = request.POST.copy()
        post_data["payer_type"] = "VENDOR"
        post_data["purpose"] = "SMS_PURCHASE"
        post_data["vendor_id"] = str(request.user.vendor.id)
        post_data["amount"] = amount
        post_data["phone"] = phone

        request.POST = post_data

        response = initiate_payment(request)

        if response.status_code != 200:
            messages.error(request, "Payment initiation failed.")
            return redirect("sms:sms_topup")

        messages.success(
            request,
            "Payment request sent. Approve it on your phone."
        )
        return redirect("vendor_dashboard")

    return render(request, "sms/topup.html", {
        "pricing": pricing,
        "wallet": wallet,
    })


@login_required
def sms_pricing_info(request):
    pricing = SMSPricing.objects.filter(is_active=True).first()
    wallet, _ = VendorSMSWallet.objects.get_or_create(vendor=request.user.vendor)

    return JsonResponse({
        "success": True,
        "price_per_sms": pricing.price_per_sms if pricing else None,
        "currency": pricing.currency if pricing else "UGX",
        "wallet_units": wallet.balance_units,
        "wallet_amount": wallet.balance_amount,
    })


@login_required
def sms_wallet_info(request):
    wallet, _ = VendorSMSWallet.objects.get_or_create(vendor=request.user.vendor)
    return JsonResponse({
        "success": True,
        "wallet_units": wallet.balance_units,
        "wallet_amount": wallet.balance_amount,
    })


@login_required
@user_passes_test(lambda user: user.is_staff)
def ugsms_balance(request):
    provider = SMSProvider.objects.filter(is_active=True).first()
    if not provider:
        return JsonResponse({"success": False, "message": "No active SMS provider"}, status=400)

    endpoint = "https://www.ugsms.com/api/v2/account/balance"
    headers = {"X-API-Key": provider.api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
        data = response.json()
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=500)

    if response.status_code >= 400:
        return JsonResponse({"success": False, "message": data.get("message", "UGSMS error")}, status=response.status_code)

    return JsonResponse(data)

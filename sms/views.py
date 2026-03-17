from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect, render
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.core.paginator import Paginator

import json
from math import ceil

import requests

from payments.views import initiate_payment
from .models import SMSPricing, VendorSMSWallet, SMSProvider, SMSLog
from .services.sms_gateway import send_bulk_sms


@login_required
def sms_topup(request):
    # Allow staff to view first vendor's SMS wallet for testing
    if request.user.is_staff:
        from accounts.models import Vendor
        vendor = Vendor.objects.filter(status='ACTIVE').first()
        if not vendor:
            messages.error(request, 'No active vendors in the system.')
            return redirect('vendor_dashboard')
    else:
        try:
            vendor = request.user.vendor
        except:
            messages.error(request, 'You are not registered as a vendor.')
            return redirect('vendor_login')
    
    pricing = SMSPricing.objects.filter(is_active=True).first()
    wallet, _ = VendorSMSWallet.objects.get_or_create(vendor=vendor)

    if request.method == "POST":
        amount = request.POST.get("amount")
        phone = request.POST.get("phone")

        if not amount or not phone:
            messages.error(request, "Amount and phone number are required.")
            return redirect("sms:sms_topup")

        if int(amount) < 500:
            messages.error(request, "Minimum amount is 500 UGX.")
            return redirect("sms:sms_topup")

        # Build a mutable POST copy for payment initiation
        post_data = request.POST.copy()
        post_data["payer_type"] = "VENDOR"
        post_data["purpose"] = "SMS_PURCHASE"
        post_data["vendor_id"] = str(vendor.id)
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
    if request.user.is_staff:
        from accounts.models import Vendor
        vendor = Vendor.objects.filter(status='ACTIVE').first()
        if not vendor:
            return JsonResponse({"success": False, "message": "No vendors"}, status=404)
    else:
        try:
            vendor = request.user.vendor
        except:
            return JsonResponse({"success": False, "message": "Not a vendor"}, status=403)
    
    pricing = SMSPricing.objects.filter(is_active=True).first()
    wallet, _ = VendorSMSWallet.objects.get_or_create(vendor=vendor)

    return JsonResponse({
        "success": True,
        "price_per_sms": pricing.price_per_sms if pricing else None,
        "currency": pricing.currency if pricing else "UGX",
        "wallet_units": wallet.balance_units,
        "wallet_amount": wallet.balance_amount,
    })


@login_required
def sms_wallet_info(request):
    if request.user.is_staff:
        from accounts.models import Vendor
        vendor = Vendor.objects.filter(status='ACTIVE').first()
        if not vendor:
            return JsonResponse({"success": False, "message": "No vendors"}, status=404)
    else:
        try:
            vendor = request.user.vendor
        except:
            return JsonResponse({"success": False, "message": "Not a vendor"}, status=403)
    
    wallet, _ = VendorSMSWallet.objects.get_or_create(vendor=vendor)
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

    endpoint = "https://ugsms.com/api/v2/account/balance"
    headers = {"X-API-Key": provider.api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
        data = response.json()
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=500)

    if response.status_code >= 400:
        return JsonResponse({"success": False, "message": data.get("message", "UGSMS error")}, status=response.status_code)

    return JsonResponse(data)


@login_required
def sms_send_bulk(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST required"}, status=405)

    if not hasattr(request.user, "vendor"):
        return JsonResponse({"success": False, "message": "Vendor account required"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON payload"}, status=400)

    messages_payload = payload.get("messages") or []
    sender_id = payload.get("sender_id")
    reference = payload.get("reference")

    if not isinstance(messages_payload, list) or not messages_payload:
        return JsonResponse({"success": False, "message": "messages array is required"}, status=400)

    normalized_messages = []
    estimated_units = 0

    for item in messages_payload:
        number = (item.get("number") or "").strip()
        message_body = (item.get("message_body") or "").strip()

        if not number or not message_body:
            return JsonResponse({"success": False, "message": "Each message needs number and message_body"}, status=400)

        normalized_messages.append({
            "number": number,
            "message_body": message_body,
        })
        estimated_units += max(1, ceil(len(message_body) / 160))

    vendor = request.user.vendor

    with transaction.atomic():
        wallet, _ = VendorSMSWallet.objects.select_for_update().get_or_create(
            vendor=vendor,
            defaults={"balance_units": 0, "balance_amount": 0},
        )

        if wallet.balance_units < estimated_units:
            return JsonResponse({
                "success": False,
                "message": f"Insufficient SMS units. Required {estimated_units}, available {wallet.balance_units}",
            }, status=400)

        wallet.balance_units -= estimated_units
        wallet.save(update_fields=["balance_units", "updated_at"])

    success, gateway_response = send_bulk_sms(
        vendor=vendor,
        messages=normalized_messages,
        sender_id=sender_id,
        reference=reference,
    )

    if not success:
        with transaction.atomic():
            wallet = VendorSMSWallet.objects.select_for_update().get(vendor=vendor)
            wallet.balance_units += estimated_units
            wallet.save(update_fields=["balance_units", "updated_at"])

        return JsonResponse({
            "success": False,
            "message": gateway_response.get("message", "Bulk SMS failed"),
            "provider_response": gateway_response,
        }, status=502)

    data = gateway_response.get("data") or {}
    summary = data.get("summary") or {}
    successful_messages = data.get("successful_messages") or []

    actual_units = 0
    for item in successful_messages:
        actual_units += int(item.get("number_of_messages") or 1)

    actual_units = max(actual_units, 0)

    with transaction.atomic():
        wallet = VendorSMSWallet.objects.select_for_update().get(vendor=vendor)

        if estimated_units > actual_units:
            wallet.balance_units += (estimated_units - actual_units)
            wallet.save(update_fields=["balance_units", "updated_at"])
        elif actual_units > estimated_units:
            extra = actual_units - estimated_units
            if wallet.balance_units >= extra:
                wallet.balance_units -= extra
                wallet.save(update_fields=["balance_units", "updated_at"])

    return JsonResponse({
        "success": True,
        "message": gateway_response.get("message", "Bulk SMS sent"),
        "estimated_units": estimated_units,
        "actual_units": actual_units,
        "summary": summary,
        "provider_response": gateway_response,
    })


@login_required
def sms_logs(request):
    try:
        vendor = request.user.vendor
    except Exception:
        return redirect('vendor_login')

    logs = SMSLog.objects.filter(vendor=vendor).order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        logs = logs.filter(status=status_filter)

    paginator = Paginator(logs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'sms/sms_logs.html', {
        'page_obj': page,
        'status_filter': status_filter,
    })

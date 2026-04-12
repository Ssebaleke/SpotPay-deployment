from decimal import Decimal
import json
from datetime import timedelta

from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone

from .models import Payment, PaymentSystemConfig, PaymentSplit
from .utils import get_active_provider, load_provider_adapter
from .services.payment_success import handle_payment_success

from sms.services.sms_topup import credit_sms_wallet
from sms.services.notifications import notify_vendor_payment_received, notify_vendor_receipt


def _parse_body(request):
    ct = (request.content_type or "").lower()
    if "application/json" in ct:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


@csrf_exempt
def initiate_payment(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    provider = get_active_provider()
    if not provider:
        return JsonResponse({"error": "No payment provider configured"}, status=400)

    data = _parse_body(request)

    try:
        amount = Decimal(str(data.get("amount")))
    except Exception:
        return JsonResponse({"error": "Invalid amount"}, status=400)

    payer_type = data.get("payer_type")
    purpose = data.get("purpose")
    phone = data.get("phone")

    if not payer_type or not purpose or not phone:
        return JsonResponse({"error": "payer_type, purpose, phone are required"}, status=400)

    # normalize legacy value
    if purpose == "VOUCHER_PURCHASE":
        purpose = "TRANSACTION"

    payment = Payment.objects.create(
        payer_type=payer_type,
        purpose=purpose,
        vendor_id=data.get("vendor_id") or None,
        location_id=data.get("location_id") or None,
        amount=amount,
        provider=provider,
        phone=phone,
        package_id=data.get("package_id") or None,
        mac_address=data.get("mac_address") or None,
        ip_address=data.get("ip_address") or None,
        currency=data.get("currency") or "UGX",
    )

    adapter = load_provider_adapter(provider)
    try:
        ref = adapter.charge(payment, data)
    except Exception as exc:
        payment.mark_failed({"reason": str(exc)})
        return JsonResponse({"error": str(exc)}, status=400)

    payment.provider_reference = ref
    payment.save(update_fields=["provider_reference"])

    return JsonResponse({
        "success": True,
        "payment_uuid": str(payment.uuid),
        "reference": ref,
        "status": payment.status,
        "status_url": f"/payments/status/{ref}/",
        "success_url": f"/payments/success/{payment.uuid}/",
        "message": "Please approve the payment on your phone."
    })


def payment_status(request, reference):
    payment = (
        Payment.objects.filter(uuid=reference).first()
        or Payment.objects.filter(provider_reference=reference).first()
    )
    if not payment:
        from django.http import Http404
        raise Http404

    # If still PENDING and using KwaPay, poll live status throttled to once per 10s
    if payment.status == "PENDING" and payment.provider and payment.provider.provider_type == "KWA":
        from django.core.cache import cache
        cache_key = f"kwa_poll_{payment.pk}"
        if not cache.get(cache_key):
            cache.set(cache_key, True, 10)
            try:
                from payments.kwa_client import KwaPayClient
                client = KwaPayClient(
                    primary_api=payment.provider.api_key,
                    secondary_api=payment.provider.api_secret,
                )
                result = client.check_status(payment.provider_reference)
                status = str(result.get("status", "")).upper()

                if status == "SUCCESSFUL" and payment.status != "SUCCESS":
                    with transaction.atomic():
                        p = Payment.objects.select_for_update().get(pk=payment.pk)
                        if p.status == "PENDING":
                            p.mark_success(result)
                            if p.purpose == "SMS_PURCHASE" and p.vendor_id:
                                try:
                                    credit_sms_wallet(vendor=p.vendor, amount_paid=int(p.amount))
                                except Exception:
                                    pass
                            if p.vendor_id:
                                if p.purpose in ("SMS_PURCHASE", "SUBSCRIPTION"):
                                    notify_vendor_receipt(p)
                                else:
                                    notify_vendor_payment_received(p)
                    payment.refresh_from_db()
                    if payment.status == "SUCCESS":
                        handle_payment_success(payment)

                elif status == "FAILED" and payment.status == "PENDING":
                    with transaction.atomic():
                        p = Payment.objects.select_for_update().get(pk=payment.pk)
                        if p.status == "PENDING":
                            p.mark_failed(result)
                    payment.refresh_from_db()

            except Exception:
                pass

    resp = {
        "success": True,
        "reference": payment.provider_reference,
        "payment_uuid": str(payment.uuid),
        "status": payment.status,
        "message": (
            "Please approve the payment on your phone."
            if payment.status == "PENDING"
            else "Payment successful."
            if payment.status == "SUCCESS"
            else "Payment failed."
        ),
    }

    if payment.status == "SUCCESS":
        voucher_code = None
        if hasattr(payment, "issued_voucher"):
            try:
                voucher_code = payment.issued_voucher.voucher.code
            except Exception:
                voucher_code = None
        # If voucher not yet assigned, try issuing it now
        if not voucher_code and payment.purpose == "TRANSACTION":
            try:
                handle_payment_success(payment)
                payment.refresh_from_db()
                if hasattr(payment, "issued_voucher"):
                    voucher_code = payment.issued_voucher.voucher.code
            except Exception:
                pass
        resp["voucher"] = voucher_code
        resp["hotspot_dns"] = payment.location.hotspot_dns if payment.location_id else "hot.spot"

    return JsonResponse(resp)


@csrf_exempt
def payment_callback(request):
    import logging
    logger = logging.getLogger(__name__)

    raw_body = request.body.decode("utf-8", errors="replace")
    logger.warning(f"MAKYPAY WEBHOOK RAW BODY: {raw_body}")
    logger.warning(f"MAKYPAY WEBHOOK HEADERS: {dict(request.headers)}")

    data = _parse_body(request)
    logger.warning(f"MAKYPAY WEBHOOK PARSED: {data}")

    txn = data.get("transaction") or {}
    reference = txn.get("reference") or txn.get("uuid")
    event_type = data.get("event_type", "")
    status_raw = txn.get("status", "").lower()

    is_success = event_type == "collection.completed" or status_raw in ("successful", "success", "completed", "paid")
    is_failed = event_type == "collection.failed" or status_raw in ("failed", "cancelled", "canceled", "rejected", "expired")

    if not reference:
        logger.warning(f"MAKYPAY WEBHOOK: no reference field found in data: {data}")
        return HttpResponse("OK")

    payment_id = None
    run_success_handler = False

    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update().filter(provider_reference=reference).first()
            or Payment.objects.select_for_update().filter(uuid=reference).first()
        )
        if not payment:
            logger.warning(f"MAKYPAY WEBHOOK: no payment found for reference={reference}")
            return HttpResponse("OK")

        if payment.status == "SUCCESS":
            return HttpResponse("OK")

        payment.raw_callback_data = data

        if is_success:
            payment.external_reference = data.get("external_reference") or payment.external_reference
            payment.processor_message = data.get("processor_message") or payment.processor_message
            payment.mark_success(data)

            if payment.purpose == "SUBSCRIPTION" and payment.location_id:
                location = payment.location
                duration_days = 30
                if location.subscription_expires_at and location.subscription_expires_at > timezone.now():
                    location.subscription_expires_at += timedelta(days=duration_days)
                else:
                    location.subscription_expires_at = timezone.now() + timedelta(days=duration_days)
                location.subscription_active = True
                location.is_active = True
                location.save(update_fields=["subscription_expires_at", "subscription_active", "is_active"])

            if payment.purpose == "SMS_PURCHASE" and payment.vendor_id:
                try:
                    credit_sms_wallet(vendor=payment.vendor, amount_paid=int(payment.amount))
                except Exception as exc:
                    payment.processor_message = f"SMS credit warning: {exc}"
                    payment.save(update_fields=["processor_message"])

            if payment.vendor_id:
                if payment.purpose in ("SMS_PURCHASE", "SUBSCRIPTION"):
                    notify_vendor_receipt(payment)
                else:
                    notify_vendor_payment_received(payment)

            payment_id = payment.id
            run_success_handler = True

        elif is_failed:
            payment.external_reference = data.get("external_reference") or payment.external_reference
            payment.processor_message = data.get("processor_message") or payment.processor_message
            payment.mark_failed(data)
        else:
            payment.save(update_fields=["raw_callback_data"])

    if run_success_handler and payment_id:
        payment = Payment.objects.get(id=payment_id)
        handle_payment_success(payment)

    return HttpResponse("OK")



def payment_success_redirect(request, uuid):
    payment = get_object_or_404(Payment, uuid=uuid)

    if payment.status != "SUCCESS":
        return HttpResponse("Payment not completed", status=400)

    if payment.purpose != "TRANSACTION":
        return HttpResponse("OK")

    voucher_code = None
    if hasattr(payment, "issued_voucher"):
        try:
            voucher_code = payment.issued_voucher.voucher.code
        except Exception:
            voucher_code = None

    if not voucher_code:
        return HttpResponse("No voucher issued for this payment", status=500)

    if not payment.location_id:
        return HttpResponse("No hotspot location attached to payment", status=400)

    location = payment.location

    auto_login_url = (
        f"http://{location.hotspot_dns}/login"
        f"?username={voucher_code}"
        f"&password={voucher_code}"
    )
    return redirect(auto_login_url)



def find_voucher(request):
    """
    GET /payments/find-voucher/?txn_id=<transaction_id>&location=<uuid>
    Looks up payment by MTN/Airtel transaction ID, returns voucher + hotspot DNS.
    """
    txn_id        = (request.GET.get('txn_id') or '').strip()
    location_uuid = (request.GET.get('location') or '').strip()

    if not txn_id or not location_uuid:
        return JsonResponse({'voucher': None, 'message': 'Transaction ID and location required.'}, status=400)

    payment = (
        Payment.objects
        .filter(provider_reference=txn_id, location__uuid=location_uuid, status='SUCCESS', purpose='TRANSACTION')
        .first()
    )

    if not payment:
        return JsonResponse({
            'voucher': None,
            'message': 'No payment found for this transaction ID. Check the ID from your MTN/Airtel SMS and try again.'
        })

    voucher_code = None
    try:
        voucher_code = payment.issued_voucher.voucher.code
    except Exception:
        pass

    if not voucher_code:
        try:
            handle_payment_success(payment)
            payment.refresh_from_db()
            voucher_code = payment.issued_voucher.voucher.code
        except Exception:
            pass

    if not voucher_code:
        return JsonResponse({'voucher': None, 'message': 'Voucher not found. Please contact support.'})

    hotspot_dns = payment.location.hotspot_dns if payment.location_id else 'hot.spot'

    return JsonResponse({
        'voucher':     voucher_code,
        'hotspot_dns': hotspot_dns,
        'message':     'Voucher found.',
    })


def payment_wait(request, reference):
    """
    GET /payments/wait/{reference}/
    External wait page — shown after payment initiation.
    Polls payment_status via JS and auto-connects via DNS redirect on success.
    Runs outside the captive portal sandbox for maximum compatibility.
    """
    from django.shortcuts import render
    status_url = f'/payments/status/{reference}/'
    return render(request, 'payments/payment_wait.html', {
        'status_url': status_url,
        'reference':  reference,
    })

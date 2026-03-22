from decimal import Decimal
import json
from datetime import timedelta

from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction

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
    ref = adapter.charge(payment, data)

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
        resp["voucher"] = voucher_code

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


@csrf_exempt
def yoo_payment_callback(request):
    import logging
    logger = logging.getLogger(__name__)

    import re
    raw_body = request.body.decode("utf-8", errors="replace")
    logger.warning(f"YOO WEBHOOK RAW BODY: {raw_body}")

    # YooPay sends XML callback
    def extract_xml(tag, body):
        match = re.search(rf"<{tag}>(.*?)</{tag}>", body)
        return match.group(1).strip() if match else None

    reference = extract_xml("InternalReference", raw_body) or extract_xml("TransactionReference", raw_body)
    status_raw = (extract_xml("TransactionStatus", raw_body) or extract_xml("Status", raw_body) or "").upper()

    data = {"raw": raw_body}
    logger.warning(f"YOO WEBHOOK reference={reference} status={status_raw}")

    is_success = status_raw in ("SUCCEEDED", "SUCCESS", "SUCCESSFUL", "COMPLETED", "APPROVED")
    is_failed = status_raw in ("FAILED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED")

    if not reference:
        logger.warning(f"YOO WEBHOOK: no reference found in data: {data}")
        return HttpResponse("OK")

    payment_id = None
    run_success_handler = False

    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update().filter(uuid=reference).first()
            or Payment.objects.select_for_update().filter(provider_reference=reference).first()
        )
        if not payment:
            logger.warning(f"YOO WEBHOOK: no payment found for reference={reference}")
            return HttpResponse("OK")

        if payment.status == "SUCCESS":
            return HttpResponse("OK")

        payment.raw_callback_data = data

        if is_success:
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

"""
payments/ipn_views.py
=====================
Yo! Payments IPN (Instant Payment Notification) handlers.

Yo! POSTs raw XML to these endpoints after a transaction settles:
  - InstantNotificationUrl → yoo_ipn()         (success)
  - FailureNotificationUrl → yoo_failure_notification()  (failure)

Both endpoints are registered in payments/urls.py:
  POST /payments/webhook/yoo/ipn/
  POST /payments/webhook/yoo/failure/

Security note:
  These endpoints are public (no auth) because Yo! does not sign requests.
  We protect against replay by checking payment.status == "SUCCESS" before
  processing and using select_for_update() inside a transaction.
"""

import logging

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from urllib.parse import parse_qs

from payments.models import Payment
from payments.services.payment_success import handle_payment_success
from sms.services.sms_topup import credit_sms_wallet
from sms.services.notifications import notify_vendor_payment_received, notify_vendor_receipt

logger = logging.getLogger(__name__)


def _parse_yoo_ipn(request) -> tuple:
    """
    Parse the raw IPN body from Yo!.
    Yo! sends IPN as URL-encoded form data (not XML).
    Returns (parsed_dict, raw_body_string).
    """
    raw = request.body.decode("utf-8", errors="replace")
    logger.warning("YOO IPN RAW: %.800s", raw)

    # Yo! IPN is URL-encoded form data
    parsed = parse_qs(raw, keep_blank_values=True)
    data = {k: v[0] for k, v in parsed.items()}

    return data, raw


def _extract_reference(data: dict, raw: str) -> str:
    """
    Extract our payment reference from the IPN data.
    Yo! sends our ExternalReference back as 'external_ref'.
    """
    # external_ref is our ExternalReference (UUID without hyphens)
    ref = data.get("external_ref") or data.get("network_ref")
    return ref if ref else None


def _find_payment(reference: str):
    """Look up Payment by UUID first, then by provider_reference.
    Also tries stripping hyphens since we send UUID without hyphens to Yo!.
    """
    # Try exact UUID match (with hyphens, Django standard)
    payment = (
        Payment.objects.select_for_update().filter(uuid=reference).first()
        or Payment.objects.select_for_update().filter(provider_reference=reference).first()
    )
    if payment:
        return payment

    # Try matching hyphen-stripped UUID (32 hex chars) back to a UUID
    if len(reference) == 32 and reference.isalnum():
        formatted = f"{reference[:8]}-{reference[8:12]}-{reference[12:16]}-{reference[16:20]}-{reference[20:]}"
        return (
            Payment.objects.select_for_update().filter(uuid=formatted).first()
            or Payment.objects.select_for_update().filter(provider_reference=reference).first()
        )

    return None


def _handle_subscription_renewal(payment):
    """Extend or activate a monthly subscription by 30 days."""
    location = payment.location
    now = timezone.now()
    if location.subscription_expires_at and location.subscription_expires_at > now:
        location.subscription_expires_at += timedelta(days=30)
    else:
        location.subscription_expires_at = now + timedelta(days=30)
    location.subscription_active = True
    location.is_active = True
    location.save(update_fields=["subscription_expires_at", "subscription_active", "is_active"])


# ---------------------------------------------------------------------------
# IPN — success notification
# ---------------------------------------------------------------------------

@csrf_exempt
def yoo_ipn(request):
    """
    POST /payments/webhook/yoo/ipn/

    Yo! calls this URL (InstantNotificationUrl) when a deposit succeeds.
    We mark the payment SUCCESS and trigger voucher issuance + SMS.
    """
    if request.method != "POST":
        return HttpResponse("OK")

    data, raw = _parse_yoo_ipn(request)

    # Yo! IPN form fields: amount, date_time, external_ref, msisdn, narrative, network_ref, signature
    # Presence of network_ref and msisdn means the transaction succeeded
    reference = _extract_reference(data, raw)
    is_success = bool(data.get("network_ref") and data.get("msisdn"))

    logger.warning(
        "YOO IPN: ref=%s network_ref=%s msisdn=%s is_success=%s",
        reference, data.get("network_ref"), data.get("msisdn"), is_success,
    )

    if not reference:
        logger.warning("YOO IPN: no reference found — ignoring")
        return HttpResponse("OK")

    if not is_success:
        logger.warning("YOO IPN: not a success notification — ignoring (use failure endpoint)")
        return HttpResponse("OK")

    payment_id = None
    run_success_handler = False

    with transaction.atomic():
        payment = _find_payment(reference)

        if not payment:
            logger.warning("YOO IPN: no payment found for reference=%s", reference)
            return HttpResponse("OK")

        if payment.status == "SUCCESS":
            return HttpResponse("OK")  # idempotent

        payment.raw_callback_data = data
        payment.mark_success(data)

        if payment.purpose == "SUBSCRIPTION" and payment.location_id:
            _handle_subscription_renewal(payment)

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

    if run_success_handler and payment_id:
        payment = Payment.objects.get(id=payment_id)
        handle_payment_success(payment)

    return HttpResponse("OK")


# ---------------------------------------------------------------------------
# KwaPay IPN
# ---------------------------------------------------------------------------

@csrf_exempt
def kwa_ipn(request):
    """
    POST /payments/webhook/kwa/ipn/
    KwaPay POSTs JSON to this URL when a transaction settles.
    """
    import json as _json

    if request.method != "POST":
        return HttpResponse("OK")

    try:
        data = _json.loads(request.body.decode("utf-8", errors="replace"))
    except Exception:
        data = {}

    logger.warning("KWA IPN: %s", data)

    reference = data.get("internal_reference")
    status = str(data.get("status", "")).upper()
    is_success = status == "SUCCESSFUL"
    is_failed = status == "FAILED"

    if not reference:
        logger.warning("KWA IPN: no internal_reference — ignoring")
        return HttpResponse("OK")

    payment_id = None
    run_success_handler = False

    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update().filter(provider_reference=reference).first()
            or Payment.objects.select_for_update().filter(uuid=reference).first()
        )

        if not payment:
            logger.warning("KWA IPN: no payment found for reference=%s", reference)
            return HttpResponse("OK")

        if payment.status == "SUCCESS":
            return HttpResponse("OK")  # idempotent

        payment.raw_callback_data = data

        if is_success:
            payment.mark_success(data)

            if payment.purpose == "SUBSCRIPTION" and payment.location_id:
                _handle_subscription_renewal(payment)

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

@csrf_exempt
def kwa_verify(request, reference):
    """
    GET /payments/kwa/verify/<reference>/
    Manually poll KwaPay check_status and complete payment if successful.
    Used when IPN callback is missed.
    """
    import json as _json
    from payments.models import PaymentProvider
    from payments.kwa_client import KwaPayClient

    payment = (
        Payment.objects.filter(provider_reference=reference).first()
        or Payment.objects.filter(uuid=reference).first()
    )

    if not payment:
        return HttpResponse("Payment not found", status=404)

    if payment.status == "SUCCESS":
        return HttpResponse("Already completed", status=200)

    provider = PaymentProvider.objects.filter(provider_type="KWA", is_active=True).first()
    if not provider:
        return HttpResponse("No KwaPay provider configured", status=400)

    client = KwaPayClient(
        primary_api=provider.api_key,
        secondary_api=provider.api_secret,
    )

    result = client.check_status(payment.provider_reference)
    logger.warning("KWA VERIFY: ref=%s result=%s", reference, result)

    status = str(result.get("status", "")).upper()
    is_success = status == "SUCCESSFUL"
    is_failed = status == "FAILED"

    payment_id = None
    run_success_handler = False

    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(
            provider_reference=payment.provider_reference
        ).first()

        if payment.status == "SUCCESS":
            return HttpResponse("Already completed", status=200)

        payment.raw_callback_data = result

        if is_success:
            payment.mark_success(result)

            if payment.purpose == "SUBSCRIPTION" and payment.location_id:
                _handle_subscription_renewal(payment)

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
            payment.mark_failed(result)
        else:
            payment.save(update_fields=["raw_callback_data"])

    if run_success_handler and payment_id:
        payment = Payment.objects.get(id=payment_id)
        handle_payment_success(payment)

    return HttpResponse(f"status={status}", status=200)


# ---------------------------------------------------------------------------
# LivePay Webhook
# ---------------------------------------------------------------------------

@csrf_exempt
def live_ipn(request):
    """
    POST /payments/webhook/live/ipn/
    LivePay POSTs JSON to this URL when a transaction settles.
    """
    import json as _json
    from payments.models import PaymentProvider
    from payments.live_client import LivePayClient

    if request.method != "POST":
        return HttpResponse("OK")

    logger.warning("LIVEPAY IPN RAW BODY: %.800s", request.body.decode('utf-8', errors='replace'))
    logger.warning("LIVEPAY IPN HEADERS: livepay-signature=%s", request.headers.get('livepay-signature', 'MISSING'))

    try:
        data = _json.loads(request.body.decode("utf-8", errors="replace"))
    except Exception:
        data = {}

    logger.warning("LIVEPAY IPN: %s", data)

    # Verify signature
    provider = PaymentProvider.objects.filter(provider_type="LIVE", is_active=True).first()
    if provider:
        signature_header = request.headers.get("livepay-signature", "")
        if signature_header:
            valid = LivePayClient.verify_webhook_signature(
                secret_key=provider.api_secret,
                signature_header=signature_header,
                payload=data,
            )
            if not valid:
                logger.warning("LIVEPAY IPN: invalid signature — rejecting")
                return HttpResponse("Invalid signature", status=401)

    # reference_id is our original reference (payment UUID without hyphens)
    reference = data.get("reference_id") or data.get("transaction_id")
    status = str(data.get("status", "")).lower()
    is_success = status == "approved"
    is_failed = status in ("failed", "cancelled")

    if not reference:
        logger.warning("LIVEPAY IPN: no reference found — ignoring")
        return HttpResponse("OK")

    payment_id = None
    run_success_handler = False

    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update().filter(provider_reference=reference).first()
            or Payment.objects.select_for_update().filter(uuid=reference).first()
        )

        # Try matching UUID without hyphens
        if not payment and len(reference) == 32:
            formatted = f"{reference[:8]}-{reference[8:12]}-{reference[12:16]}-{reference[16:20]}-{reference[20:]}"
            payment = Payment.objects.select_for_update().filter(uuid=formatted).first()

        if not payment:
            logger.warning("LIVEPAY IPN: no payment found for reference=%s", reference)
            return HttpResponse("OK")

        if payment.status == "SUCCESS":
            return HttpResponse("OK")  # idempotent

        payment.raw_callback_data = data

        if is_success:
            payment.mark_success(data)

            if payment.purpose == "SUBSCRIPTION" and payment.location_id:
                _handle_subscription_renewal(payment)

            if payment.purpose == "SMS_PURCHASE" and payment.vendor_id:
                try:
                    credit_sms_wallet(vendor=payment.vendor, amount_paid=int(float(payment.amount)))
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

    return HttpResponse(
        _json.dumps({"status": "received", "message": "Webhook processed successfully"}),
        content_type="application/json"
    )


@csrf_exempt
def yoo_failure_notification(request):
    """
    POST /payments/webhook/yoo/failure/

    Yo! calls this URL (FailureNotificationUrl) when a deposit fails.
    We mark the payment FAILED.
    """
    if request.method != "POST":
        return HttpResponse("OK")

    data, raw = _parse_yoo_ipn(request)

    # Yo! failure notification fields: failed_transaction_reference, transaction_init_date, verification
    reference = data.get("failed_transaction_reference") or _extract_reference(data, raw)

    logger.warning(
        "YOO FAILURE IPN: ref=%s data=%s",
        reference, data,
    )

    if not reference:
        logger.warning("YOO FAILURE IPN: no reference found — ignoring")
        return HttpResponse("OK")

    with transaction.atomic():
        payment = _find_payment(reference)

        if not payment:
            logger.warning("YOO FAILURE IPN: no payment found for reference=%s", reference)
            return HttpResponse("OK")

        if payment.status in ("SUCCESS", "FAILED"):
            return HttpResponse("OK")  # idempotent

        payment.raw_callback_data = data
        payment.mark_failed(data)

    return HttpResponse("OK")

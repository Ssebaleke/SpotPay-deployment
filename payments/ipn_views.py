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
import re

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta

from payments.models import Payment
from payments.yoo_client import YoPaymentsClient
from payments.services.payment_success import handle_payment_success
from sms.services.sms_topup import credit_sms_wallet
from sms.services.notifications import notify_vendor_payment_received, notify_vendor_receipt

logger = logging.getLogger(__name__)

_client = YoPaymentsClient.__new__(YoPaymentsClient)  # parse-only, no credentials needed


def _parse_yoo_ipn(request) -> tuple[dict, str]:
    """
    Parse the raw IPN body from Yo!.
    Returns (parsed_dict, raw_body_string).
    Yo! sends XML; fall back to form-encoded if not XML.
    """
    raw = request.body.decode("utf-8", errors="replace")
    logger.warning("YOO IPN RAW: %.800s", raw)

    if raw.strip().startswith("<"):
        data = YoPaymentsClient._parse_xml_response(_client, raw)
    else:
        import json
        try:
            data = json.loads(raw or "{}")
        except Exception:
            data = dict(request.POST)

    return data, raw


def _extract_reference(data: dict, raw: str) -> str | None:
    """
    Extract the payment reference from the IPN data.

    Yo! may send:
      - TransactionReference  (their reference)
      - InternalReference     (our UUID, embedded in the XML)
    We prefer InternalReference because that maps directly to Payment.uuid.
    """
    # Try InternalReference first (our UUID)
    match = re.search(r"<InternalReference>(.*?)</InternalReference>", raw)
    if match:
        return match.group(1).strip()

    return (
        data.get("transaction_reference")
        or data.get("mno_reference")
    )


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

    status        = str(data.get("status") or "").upper()
    status_code   = str(data.get("status_code") or "")
    txn_status    = str(data.get("transaction_status") or "").upper()

    is_success = (
        (status == "OK" and status_code == "0")
        or txn_status in {"SUCCEEDED", "SUCCESS", "SUCCESSFUL", "COMPLETED", "APPROVED"}
    )

    reference = _extract_reference(data, raw)

    logger.warning(
        "YOO IPN: ref=%s status=%s txn_status=%s is_success=%s",
        reference, status, txn_status, is_success,
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
# Failure notification
# ---------------------------------------------------------------------------

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

    txn_status = str(data.get("transaction_status") or "").upper()
    reference  = _extract_reference(data, raw)

    logger.warning(
        "YOO FAILURE IPN: ref=%s txn_status=%s",
        reference, txn_status,
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

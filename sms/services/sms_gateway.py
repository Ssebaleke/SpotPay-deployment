from sms.models import SMSProvider, SMSLog
import requests


def _active_provider():
    return SMSProvider.objects.filter(is_active=True).first()


def _is_ugsms_provider(provider):
    return (provider.provider_type or "").upper() in ("UGSMS", "YOUGANDA")


def _format_phone_ugsms(phone):
    """UGSMS accepts 07XXXXXXXX or +256XXXXXXXXX format"""
    phone = (phone or "").strip()
    if phone.startswith("+256"):
        phone = "0" + phone[4:]
    elif phone.startswith("256") and len(phone) == 12:
        phone = "0" + phone[3:]
    return phone


def send_sms(*, vendor, phone, message, purpose=None, voucher_code=None, payment=None):
    provider = _active_provider()

    if not provider:
        SMSLog.objects.create(
            vendor=vendor,
            phone=phone,
            message=message,
            voucher_code=voucher_code,
            payment=payment,
            status="FAILED",
            failure_reason="No active SMS provider",
        )
        return False, "No active SMS provider"

    try:
        provider_type = (provider.provider_type or "").upper()

        if _is_ugsms_provider(provider):
            endpoint = "https://ugsms.com/api/v2/sms/send"
            payload = {
                "numbers": _format_phone_ugsms(phone),
                "message_body": message,
                "sender_id": provider.sender_id,
            }
            headers = {
                "X-API-Key": provider.api_key,
                "Content-Type": "application/json",
            }

            api_response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=15,
            )

            response_json = {}
            try:
                response_json = api_response.json()
            except Exception:
                response_json = {"message": api_response.text}

            if api_response.status_code >= 400 or not response_json.get("success"):
                raise ValueError(response_json.get("message") or "UGSMS send failed")

            response = response_json.get("message") or "SMS sent"
        else:
            raise ValueError(f"SMS provider '{provider_type}' not yet integrated")

        SMSLog.objects.create(
            vendor=vendor,
            phone=phone,
            message=message,
            voucher_code=voucher_code,
            payment=payment,
            provider=provider,
            status="SENT",
        )

        return True, response

    except Exception as e:
        SMSLog.objects.create(
            vendor=vendor,
            phone=phone,
            message=message,
            voucher_code=voucher_code,
            payment=payment,
            provider=provider,
            status="FAILED",
            failure_reason=str(e),
        )
        return False, str(e)


def send_bulk_sms(*, vendor, messages, sender_id=None, reference=None):
    provider = _active_provider()

    if not provider:
        return False, {"message": "No active SMS provider", "data": None}

    try:
        provider_type = (provider.provider_type or "").upper()
        if not _is_ugsms_provider(provider):
            raise ValueError(f"SMS provider '{provider_type}' not yet integrated")

        endpoint = "https://ugsms.com/api/v2/sms/send/bulk"
        payload = {
            "messages": messages,
            "sender_id": sender_id or provider.sender_id,
        }
        if reference:
            payload["reference"] = reference

        headers = {
            "X-API-Key": provider.api_key,
            "Content-Type": "application/json",
        }

        api_response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=20,
        )

        response_json = {}
        try:
            response_json = api_response.json()
        except Exception:
            response_json = {"message": api_response.text}

        if api_response.status_code >= 400:
            raise ValueError(response_json.get("message") or "UGSMS bulk send failed")

        data = response_json.get("data") or {}
        successful_messages = data.get("successful_messages") or []
        failed_messages = data.get("failed_messages") or []

        for item in successful_messages:
            index = item.get("index")
            phone = messages[index]["number"] if index is not None and index < len(messages) else "UNKNOWN"
            body = messages[index]["message_body"] if index is not None and index < len(messages) else ""
            SMSLog.objects.create(
                vendor=vendor,
                phone=phone,
                message=body,
                provider=provider,
                status="SENT",
            )

        for item in failed_messages:
            index = item.get("index")
            phone = messages[index]["number"] if index is not None and index < len(messages) else "UNKNOWN"
            body = messages[index]["message_body"] if index is not None and index < len(messages) else ""
            SMSLog.objects.create(
                vendor=vendor,
                phone=phone,
                message=body,
                provider=provider,
                status="FAILED",
            )

        if not response_json.get("success"):
            return False, response_json

        return True, response_json

    except Exception as exc:
        return False, {"message": str(exc), "data": None}

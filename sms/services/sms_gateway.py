from sms.models import SMSProvider, SMSLog
import requests


def send_sms(*, vendor, phone, message, purpose=None):
    provider = SMSProvider.objects.filter(is_active=True).first()

    if not provider:
        SMSLog.objects.create(
            vendor=vendor,
            phone=phone,
            message=message,
            status="FAILED",
        )
        return False, "No active SMS provider"

    try:
        provider_type = (provider.provider_type or "").upper()

        if provider_type in ("UGSMS", "YOUGANDA"):
            endpoint = "https://www.ugsms.com/api/v2/sms/send"
            payload = {
                "numbers": phone,
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
            provider=provider,
            status="SENT",
        )

        return True, response

    except Exception as e:
        SMSLog.objects.create(
            vendor=vendor,
            phone=phone,
            message=message,
            provider=provider,
            status="FAILED",
        )
        return False, str(e)

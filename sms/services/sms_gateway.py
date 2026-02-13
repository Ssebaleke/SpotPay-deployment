from sms.models import SMSProvider, SMSLog


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
        # API INTEGRATION WILL GO HERE LATER
        response = f"Mock SMS sent via {provider.name}"

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

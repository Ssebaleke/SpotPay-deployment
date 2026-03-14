import requests

from sms.models import EmailProvider


def send_email(*, to_email, subject, html=None, text=None):
    provider = EmailProvider.objects.filter(is_active=True).first()

    if not provider:
        return False, "No active email provider"

    provider_type = (provider.provider_type or "").upper()

    if provider_type != "RESEND":
        return False, f"Email provider '{provider_type}' not supported"

    if not html and not text:
        return False, "Either html or text content is required"

    payload = {
        "from": provider.from_email,
        "to": [to_email],
        "subject": subject,
    }
    if html:
        payload["html"] = html
    if text:
        payload["text"] = text

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {provider.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        data = {}
        try:
            data = response.json()
        except Exception:
            data = {"message": response.text}

        if response.status_code >= 400:
            return False, data.get("message", "Resend request failed")

        return True, data.get("id", "sent")
    except Exception as exc:
        return False, str(exc)

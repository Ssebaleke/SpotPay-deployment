import logging
import requests

from sms.models import EmailProvider

logger = logging.getLogger(__name__)


def send_email(*, to_email, subject, html=None, text=None):
    if not html and not text:
        return False, "Either html or text content is required"

    provider = EmailProvider.objects.filter(is_active=True).first()

    # --- Resend API path ---
    if provider and (provider.provider_type or "").upper() == "RESEND":
        payload = {
            "from": provider.from_email,
            "to": [to_email],
            "subject": subject,
        }
        if html:
            payload["html"] = html
        if text:
            payload["text"] = text
        logger.warning(f"RESEND: sending to={to_email} subject='{subject}' from={provider.from_email}")
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
            logger.warning(f"RESEND: status={response.status_code} response={data}")
            if response.status_code >= 400:
                return False, data.get("message", "Resend request failed")
            return True, data.get("id", "sent")
        except Exception as exc:
            logger.error(f"RESEND: exception={exc}")
            return False, str(exc)

    # --- Django SMTP fallback (uses EMAIL_* settings from .env) ---
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    from_email = settings.DEFAULT_FROM_EMAIL
    msg = EmailMultiAlternatives(subject, text or "", from_email, [to_email])
    if html:
        msg.attach_alternative(html, "text/html")
    try:
        msg.send()
        return True, "sent"
    except Exception as exc:
        return False, str(exc)

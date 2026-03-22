import logging
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger(__name__)


class YooAdapter:
    """
    Yo! Payments (YooPay) - Collections
    API uses XML over HTTPS POST
    """

    def __init__(self, provider):
        self.provider = provider
        self.base_url = (provider.base_url or "").rstrip("/")
        self.username = (provider.api_key or "").strip()
        self.password = (provider.api_secret or "").strip()

        if not self.base_url:
            raise ValueError("PaymentProvider.base_url is missing")
        if not self.username or not self.password:
            raise ValueError("YooPay requires username (api_key) and password (api_secret).")

    def charge(self, payment, data: dict):
        phone = (data.get("phone") or data.get("phone_number") or "").strip()
        if not phone:
            raise ValueError("Phone number is required")

        amt = data.get("amount", None)
        if amt is None:
            amt = payment.amount
        amount_int = int(Decimal(str(amt)))

        # Normalize phone: YooPay expects 256XXXXXXXXX
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "256" + phone[1:]
        if not phone.startswith("256"):
            phone = "256" + phone

        webhook_url = f"{settings.SITE_URL}/payments/webhook/yoo/"
        reference = str(payment.uuid)

        xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<AutoCreate>
  <Request>
    <APIUsername>{self.username}</APIUsername>
    <APIPassword>{self.password}</APIPassword>
    <Method>acdepositfunds</Method>
    <Account>{phone}</Account>
    <Amount>{amount_int}</Amount>
    <Currency>UGX</Currency>
    <Narrative>Payment for internet voucher</Narrative>
    <InternalReference>{reference}</InternalReference>
    <CallbackURL>{webhook_url}</CallbackURL>
    <NonBlocking>FALSE</NonBlocking>
  </Request>
</AutoCreate>"""

        url = f"{self.base_url}/services/yoPaymentService"

        logger.warning(f"YOO CHARGE REQUEST: url={url} phone={phone} amount={amount_int}")

        resp = requests.post(
            url,
            data=xml_payload,
            headers={"Content-Type": "text/xml; charset=utf-8"},
            timeout=60,
        )

        logger.warning(f"YOO CHARGE RESPONSE: status={resp.status_code} body={resp.text[:500]}")

        if resp.status_code >= 400:
            raise ValueError(f"YooPay {resp.status_code}: {resp.text}")

        # YooPay responds with XML - extract TransactionReference
        import re
        provider_reference = None

        match = re.search(r"<TransactionReference>(.*?)</TransactionReference>", resp.text)
        if match:
            provider_reference = match.group(1).strip()

        if not provider_reference:
            match = re.search(r"<InternalReference>(.*?)</InternalReference>", resp.text)
            if match:
                provider_reference = match.group(1).strip()

        logger.warning(f"YOO provider_reference={provider_reference or '(fallback to uuid)'}")

        return str(provider_reference or payment.uuid)

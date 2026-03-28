from django.db import transaction
from sms.models import VendorSMSWallet
from .sms_gateway import send_sms


@transaction.atomic
def send_voucher_sms(*, vendor, phone, voucher_code, package_name, payment=None, location=None):
    wallet, _ = VendorSMSWallet.objects.select_for_update().get_or_create(
        vendor=vendor,
        defaults={"balance_units": 0, "balance_amount": 0}
    )

    if wallet.balance_units < 1:
        from sms.models import SMSLog
        SMSLog.objects.create(
            vendor=vendor,
            phone=phone,
            message=f"UNSENT - Insufficient SMS balance. Voucher: {voucher_code}",
            voucher_code=voucher_code,
            payment=payment,
            status="FAILED",
            failure_reason="Insufficient SMS balance",
        )
        return False, "Insufficient SMS balance"

    location_name = location.site_name if location else vendor.company_name
    dns = (location.hotspot_dns or "hot.spot") if location else "hot.spot"
    connect_link = f"http://{dns}/login?username={voucher_code}&password={voucher_code}&dst=http://{dns}"

    message = (
        f"{location_name} WiFi\n"
        f"Package: {package_name}\n"
        f"Voucher: {voucher_code}\n"
        f"Tap to connect: {connect_link}"
    )

    success, response = send_sms(
        vendor=vendor,
        phone=phone,
        message=message,
        purpose="VOUCHER_ISSUED",
        voucher_code=voucher_code,
        payment=payment,
    )

    if not success:
        return False, response

    wallet.balance_units -= 1
    wallet.save(update_fields=["balance_units"])

    return True, "Voucher SMS sent successfully"

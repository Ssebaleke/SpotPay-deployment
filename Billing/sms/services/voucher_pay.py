from django.db import transaction
from sms.models import VendorSMSWallet
from .sms_gateway import send_sms


@transaction.atomic
def send_voucher_sms(*, vendor, phone, voucher_code, package_name):
    wallet, _ = VendorSMSWallet.objects.select_for_update().get_or_create(
        vendor=vendor,
        defaults={
            "balance_units": 0,
            "balance_amount": 0,
        }
    )

    if wallet.balance_units < 1:
        return False, "Insufficient SMS balance"

    message = (
        "Your WiFi voucher is ready.\n"
        f"Code: {voucher_code}\n"
        f"Package: {package_name}"
    )

    success, response = send_sms(
        vendor=vendor,
        phone=phone,
        message=message,
        purpose="VOUCHER_ISSUED",
    )

    if not success:
        return False, response

    wallet.balance_units -= 1
    wallet.save(update_fields=["balance_units"])

    return True, "Voucher SMS sent successfully"

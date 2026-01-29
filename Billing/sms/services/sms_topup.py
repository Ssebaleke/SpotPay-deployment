from django.db import transaction

from sms.models import (
    VendorSMSWallet,
    SMSPricing,
    SMSPurchase,
)


@transaction.atomic
def credit_sms_wallet(*, vendor, amount_paid):
    """
    Credit vendor SMS wallet after SUCCESSFUL internal payment
    """

    # 1. Get active SMS pricing
    pricing = SMSPricing.objects.filter(is_active=True).first()
    if not pricing:
        raise ValueError("No active SMS pricing configured")

    # 2. Calculate SMS units
    sms_units = amount_paid // pricing.price_per_sms
    if sms_units < 1:
        raise ValueError("Amount too low to buy SMS units")

    # 3. Get vendor SMS wallet (always exists via signal)
    wallet = VendorSMSWallet.objects.select_for_update().get(
        vendor=vendor
    )

    # 4. Credit wallet
    wallet.balance_units += sms_units
    wallet.balance_amount += amount_paid
    wallet.save(update_fields=["balance_units", "balance_amount"])

    # 5. Record purchase (audit trail)
    SMSPurchase.objects.create(
        vendor=vendor,
        amount_paid=amount_paid,
        sms_units_credited=sms_units,
        price_per_sms=pricing.price_per_sms,
        status="SUCCESS",
    )

    return {
        "sms_units": sms_units,
        "new_balance": wallet.balance_units,
    }

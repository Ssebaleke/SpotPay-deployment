from decimal import Decimal, ROUND_HALF_UP


def calculate_fees(payment, billing):
    """
    Core revenue logic.

    Returns a dict:
    {
        'gross_amount': Decimal,
        'platform_fee': Decimal,
        'vendor_amount': Decimal,
        'percentage_used': Decimal
    }
    """

    gross_amount = Decimal(payment.amount)

    # Safety: percentage must exist
    percentage = Decimal(billing.transaction_percentage or 0)

    # Platform cut
    platform_fee = (
        gross_amount * (percentage / Decimal('100'))
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Vendor receives the rest
    vendor_amount = (gross_amount - platform_fee).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP
    )

    return {
        'gross_amount': gross_amount,
        'platform_fee': platform_fee,
        'vendor_amount': vendor_amount,
        'percentage_used': percentage,
    }

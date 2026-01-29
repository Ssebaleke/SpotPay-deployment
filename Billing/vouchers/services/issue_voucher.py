# vouchers/services/issue_voucher.py

from vouchers.models import Voucher


def issue_voucher(*, vendor, package):
    """
    Automatically issues a voucher after payment success
    """

    voucher = Voucher.objects.create(
        vendor=vendor,
        package=package,
        is_used=False,
    )

    return voucher

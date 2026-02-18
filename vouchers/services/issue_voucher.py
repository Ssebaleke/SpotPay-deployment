from django.db import transaction
from django.utils import timezone

from vouchers.models import Voucher


class NoAvailableVouchers(Exception):
    pass


@transaction.atomic
def issue_voucher(vendor, package):
    """
    Reserve ONE UNUSED voucher for a given package.
    Safe under high traffic:
    - locks row with SELECT ... FOR UPDATE
    - prevents two users from receiving same voucher
    """

    # lock a single unused voucher
    voucher = (
        Voucher.objects
        .select_for_update(skip_locked=True)
        .filter(package=package, status="UNUSED")
        .order_by("id")
        .first()
    )

    if not voucher:
        raise NoAvailableVouchers("No unused vouchers available for this package.")

    # reserve it immediately
    voucher.status = "RESERVED"
    voucher.save(update_fields=["status"])

    return voucher

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Vendor
from sms.models import VendorSMSWallet


@receiver(post_save, sender=Vendor)
def create_sms_wallet(sender, instance, created, **kwargs):
    if created:
        VendorSMSWallet.objects.create(
            vendor=instance,
            balance_units=0,
            balance_amount=0,
        )

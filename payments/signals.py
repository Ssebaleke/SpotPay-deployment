from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal

from hotspot.models import HotspotLocation
from .models import LocationBillingProfile, Payment


# =====================================================
# AUTO-CREATE BILLING PROFILE FOR EVERY LOCATION
# =====================================================

@receiver(post_save, sender=HotspotLocation)
def create_billing_profile(sender, instance, created, **kwargs):
    if created:
        LocationBillingProfile.objects.create(
            location=instance,
            subscription_required=True,
            subscription_fee=Decimal('50000.00'),
            transaction_percentage=Decimal('5.00'),
        )


# =====================================================
# HANDLE SUCCESSFUL SUBSCRIPTION PAYMENT
# =====================================================

@receiver(post_save, sender=Payment)
def handle_subscription_payment(sender, instance, created, **kwargs):
    if instance.status != 'success':
        return

    if instance.payment_type != 'SUBSCRIPTION':
        return

    billing = instance.location.billing

    billing.subscription_expires_at = (
        timezone.now() +
        timezone.timedelta(days=billing.subscription_period_days)
    )

    billing.save(update_fields=['subscription_expires_at'])

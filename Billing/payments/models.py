from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid


# =====================================================
# 1. PAYMENT PROVIDERS (ADMIN CONFIGURED)
# =====================================================
# API keys & endpoints live in DB (no hardcoding)

class PaymentProvider(models.Model):
    PROVIDER_TYPES = (
        ('MOMO', 'Mobile Money'),
        ('CARD', 'Card / Gateway'),
    )

    name = models.CharField(max_length=50)   # MTN, Airtel, Flutterwave
    provider_type = models.CharField(
        max_length=10,
        choices=PROVIDER_TYPES
    )

    is_active = models.BooleanField(default=False)

    # Store API keys, secrets, URLs, etc
    config = models.JSONField(
        help_text="API credentials & endpoints"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "ACTIVE" if self.is_active else "INACTIVE"
        return f"{self.name} ({status})"


# =====================================================
# 2. LOCATION BILLING PROFILE (AUTO-CREATED)
# =====================================================
# EVERY location has this
# Created automatically when a location is added

class LocationBillingProfile(models.Model):
    location = models.OneToOneField(
        'hotspot.HotspotLocation',
        on_delete=models.CASCADE,
        related_name='billing'
    )

    # ---------- SUBSCRIPTION ----------
    subscription_required = models.BooleanField(
        default=True,
        help_text="If false, no monthly subscription is required"
    )

    subscription_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('50000.00')
    )

    subscription_period_days = models.PositiveIntegerField(
        default=30,
        help_text="How long a subscription lasts after payment"
    )

    subscription_expires_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # ---------- TRANSACTION CUT ----------
    transaction_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text="Platform percentage cut per transaction"
    )

    # ---------- CONTROL ----------
    is_active = models.BooleanField(
        default=True,
        help_text="Disable all platform services for this location"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---------- HELPERS ----------

    def subscription_valid(self):
        """
        Returns True if:
        - subscription is NOT required, OR
        - subscription is required and still valid
        """
        if not self.subscription_required:
            return True

        if not self.subscription_expires_at:
            return False

        return self.subscription_expires_at > timezone.now()

    def extend_subscription(self):
        """
        Extend subscription after successful payment.
        """
        now = timezone.now()

        if self.subscription_expires_at and self.subscription_expires_at > now:
            self.subscription_expires_at += timezone.timedelta(
                days=self.subscription_period_days
            )
        else:
            self.subscription_expires_at = now + timezone.timedelta(
                days=self.subscription_period_days
            )

        self.save(update_fields=['subscription_expires_at'])

    def __str__(self):
        return f"Billing for {self.location.site_name}"


# =====================================================
# 3. PAYMENTS (SOURCE OF TRUTH)
# =====================================================
# ALL money events go through here

class Payment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    )

    PAYMENT_TYPES = (
        ('VOUCHER', 'Voucher Purchase'),
        ('SUBSCRIPTION', 'Subscription Payment'),
    )

    reference = models.CharField(
        max_length=100,
        unique=True,
        default=uuid.uuid4
    )

    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPES
    )

    phone_number = models.CharField(
        max_length=15,
        help_text="Phone number used to pay"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    vendor = models.ForeignKey(
        'accounts.Vendor',
        on_delete=models.CASCADE
    )

    location = models.ForeignKey(
        'hotspot.HotspotLocation',
        on_delete=models.CASCADE
    )

    provider = models.ForeignKey(
        PaymentProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---------- BUSINESS ACTION ----------

    def mark_successful(self):
        """
        Called when payment provider confirms success.
        """
        if self.status == self.STATUS_SUCCESS:
            return

        self.status = self.STATUS_SUCCESS
        self.save(update_fields=['status'])

        # Apply subscription payment
        if self.payment_type == 'SUBSCRIPTION':
            billing = self.location.billing
            billing.extend_subscription()

    def __str__(self):
        return (
            f"{self.reference} | "
            f"{self.payment_type} | "
            f"{self.amount} | "
            f"{self.status}"
        )


# =====================================================
# 4. HELPERS (USED BY OTHER APPS)
# =====================================================

def create_default_location_billing(location):
    """
    Create billing profile for a newly created location.
    This is called ONCE when location is added.
    """
    return LocationBillingProfile.objects.create(
        location=location
    )

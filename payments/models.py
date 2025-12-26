from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid


# =====================================================
# PAYMENT PROVIDERS
# =====================================================

class PaymentProvider(models.Model):
    PROVIDER_TYPES = (
        ('MOMO', 'Mobile Money'),
        ('CARD', 'Card / Gateway'),
    )

    name = models.CharField(max_length=50)
    provider_type = models.CharField(max_length=10, choices=PROVIDER_TYPES)
    is_active = models.BooleanField(default=False)
    config = models.JSONField(help_text="API keys, secrets, endpoints")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# =====================================================
# LOCATION BILLING PROFILE
# =====================================================

class LocationBillingProfile(models.Model):

    # 🔑 SUBSCRIPTION MODES (ONLY A & C)
    MODE_SUBSCRIPTION_ONLY = 'SUB_ONLY'
    MODE_SUBSCRIPTION_PLUS_PERCENT = 'SUB_PLUS_PERCENT'

    SUBSCRIPTION_MODES = (
        (MODE_SUBSCRIPTION_ONLY, 'Subscription Only'),
        (MODE_SUBSCRIPTION_PLUS_PERCENT, 'Subscription + Transaction Percentage'),
    )

    location = models.OneToOneField(
        'hotspot.HotspotLocation',
        on_delete=models.CASCADE,
        related_name='billing'
    )

    # ---------- MODE (ADMIN SETS THIS) ----------
    subscription_mode = models.CharField(
        max_length=30,
        choices=SUBSCRIPTION_MODES,
        default=MODE_SUBSCRIPTION_ONLY
    )

    # ---------- SUBSCRIPTION ----------
    subscription_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('50000.00')
    )

    subscription_period_days = models.PositiveIntegerField(default=30)

    subscription_expires_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # ---------- TRANSACTION CUT (USED ONLY IN MODE C) ----------
    transaction_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Used ONLY when mode is Subscription + Percentage"
    )

    # ---------- CONTROL ----------
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---------- HELPERS ----------
    def subscription_valid(self):
        if not self.subscription_expires_at:
            return False
        return self.subscription_expires_at > timezone.now()

    def platform_cut_enabled(self):
        return self.subscription_mode == self.MODE_SUBSCRIPTION_PLUS_PERCENT

    def __str__(self):
        return f"{self.location.site_name} Billing"


# =====================================================
# PAYMENTS
# =====================================================

class Payment(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_SUCCESS = 'SUCCESS'
    STATUS_FAILED = 'FAILED'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    )

    PAYMENT_TYPES = (
        ('SUBSCRIPTION', 'Subscription'),
        ('VOUCHER', 'Voucher Purchase'),
    )

    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPES
    )

    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

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

    def __str__(self):
        return f"{self.reference} | {self.payment_type} | {self.status}"

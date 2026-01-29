from django.db import models
from django.utils import timezone
import uuid


# =====================================================
# PAYMENT PROVIDERS (ADMIN CONFIGURED)
# =====================================================

class PaymentProvider(models.Model):
    PROVIDER_TYPES = (
        ('MOMO', 'Mobile Money'),
        ('CARD', 'Card / Gateway'),
    )

    ENVIRONMENTS = (
        ('SANDBOX', 'Sandbox'),
        ('LIVE', 'Live'),
    )

    name = models.CharField(max_length=50)
    provider_type = models.CharField(max_length=10, choices=PROVIDER_TYPES)

    base_url = models.URLField()
    api_key = models.CharField(max_length=255)
    api_secret = models.CharField(max_length=255, blank=True)

    environment = models.CharField(
        max_length=10,
        choices=ENVIRONMENTS,
        default='SANDBOX'
    )

    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.is_active:
            PaymentProvider.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.environment})"


# =====================================================
# GLOBAL SYSTEM CONFIG (ONE ROW ONLY)
# =====================================================

class PaymentSystemConfig(models.Model):
    base_system_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Base commission applied to ALL transactions (e.g. 5%)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "System Payment Configuration"


# =====================================================
# PAYMENT (SINGLE SOURCE OF TRUTH)
# =====================================================

class Payment(models.Model):
    PURPOSES = (
        ('SUBSCRIPTION', 'Location Subscription'),
        ('TRANSACTION', 'Client Internet Purchase'),
        ('SMS_PURCHASE', 'SMS Purchase'),
    )

    PAYER_TYPES = (
        ('VENDOR', 'Vendor'),
        ('CLIENT', 'Client'),
    )

    STATUSES = (
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    payer_type = models.CharField(max_length=10, choices=PAYER_TYPES)
    purpose = models.CharField(max_length=20, choices=PURPOSES)

    vendor = models.ForeignKey(
        'accounts.Vendor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    location = models.ForeignKey(
        'hotspot.HotspotLocation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    provider = models.ForeignKey(
        PaymentProvider,
        on_delete=models.SET_NULL,
        null=True
    )

    provider_reference = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=STATUSES,
        default='PENDING'
    )

    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    raw_callback_data = models.JSONField(null=True, blank=True)

    def mark_success(self, data=None):
        if self.status == 'SUCCESS':
            return
        self.status = 'SUCCESS'
        self.completed_at = timezone.now()
        if data:
            self.raw_callback_data = data
        self.save()

    def mark_failed(self, data=None):
        self.status = 'FAILED'
        if data:
            self.raw_callback_data = data
        self.save()

    def __str__(self):
        return f"{self.purpose} | {self.amount} | {self.status}"


# =====================================================
# TRANSACTION SPLIT (AUDIT SAFE)
# =====================================================

class PaymentSplit(models.Model):
    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name='split'
    )

    base_system_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    subscription_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    admin_amount = models.DecimalField(max_digits=12, decimal_places=2)
    vendor_amount = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Split for {self.payment.uuid}"

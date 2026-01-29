from django.db import models
from django.utils import timezone
from accounts.models import Vendor


# =====================================================
# 1. SMS PROVIDERS (ADMIN CONFIGURATION)
# =====================================================
# Admin can add multiple providers
# Only ONE can be active at a time

class SMSProvider(models.Model):
    PROVIDER_TYPES = (
        ("AFRICASTALKING", "Africa's Talking"),
        ("YOUGANDA", "Yo! Uganda"),
        ("TWILIO", "Twilio"),
        ("OTHER", "Other"),
    )

    name = models.CharField(max_length=50)
    provider_type = models.CharField(
        max_length=30,
        choices=PROVIDER_TYPES
    )

    api_key = models.CharField(max_length=255)
    api_secret = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    sender_id = models.CharField(
        max_length=20,
        help_text="Sender ID or short code"
    )

    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Ensure ONLY one provider is active
        if self.is_active:
            SMSProvider.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        status = "ACTIVE" if self.is_active else "INACTIVE"
        return f"{self.name} ({status})"


# =====================================================
# 2. SMS PRICING (ADMIN SETS COST PER SMS)
# =====================================================
# Vendors buy SMS using MONEY
# Admin decides how much ONE SMS costs

class SMSPricing(models.Model):
    price_per_sms = models.PositiveIntegerField(
        help_text="Cost per SMS in UGX"
    )
    currency = models.CharField(
        max_length=10,
        default="UGX"
    )

    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Ensure ONLY one pricing is active
        if self.is_active:
            SMSPricing.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.price_per_sms} {self.currency} per SMS"


# =====================================================
# 3. VENDOR SMS WALLET (PREPAID SYSTEM)
# =====================================================
# Vendors buy SMS using MONEY (e.g. 5,000 UGX)
# System converts money → SMS units

class VendorSMSWallet(models.Model):
    vendor = models.OneToOneField(
        Vendor,
        on_delete=models.CASCADE,
        related_name="sms_wallet"
    )

    # Accounting (money paid by vendor)
    balance_amount = models.PositiveIntegerField(
        default=0,
        help_text="Total money paid for SMS (UGX)"
    )

    # Operational (actual SMS available)
    balance_units = models.PositiveIntegerField(
        default=0,
        help_text="Number of SMS units available"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.vendor} | "
            f"{self.balance_units} SMS | "
            f"{self.balance_amount} UGX"
        )


# =====================================================
# 4. SMS PURCHASE TRANSACTIONS (AUDIT TRAIL)
# =====================================================
# Every vendor SMS purchase is recorded

class SMSPurchase(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
    )

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE
    )

    amount_paid = models.PositiveIntegerField(
        help_text="Amount paid by vendor (UGX)"
    )

    sms_units_credited = models.PositiveIntegerField(
        help_text="SMS units credited after payment"
    )

    price_per_sms = models.PositiveIntegerField(
        help_text="SMS price used at time of purchase (UGX)"
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.vendor} | "
            f"{self.sms_units_credited} SMS | "
            f"{self.status}"
        )


# =====================================================
# 5. SMS LOG (OPTIONAL BUT RECOMMENDED)
# =====================================================
# Tracks every SMS sent by the system

class SMSLog(models.Model):
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE
    )

    phone = models.CharField(max_length=20)
    message = models.TextField()

    provider = models.ForeignKey(
        SMSProvider,
        on_delete=models.SET_NULL,
        null=True
    )

    status = models.CharField(
        max_length=20,
        default="SENT"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SMS to {self.phone} ({self.status})"

from django.db import models
from django.utils import timezone
import uuid


# =====================================================
# PAYMENT PROVIDERS (ADMIN CONFIGURED)
# =====================================================

class PaymentProvider(models.Model):
    PROVIDER_TYPES = (
        ("MOMO", "Mobile Money (MakyPay)"),
        ("CARD", "Card / Gateway"),
        ("YOO", "Mobile Money (YooPay)"),
    )

    ENVIRONMENTS = (
        ("SANDBOX", "Sandbox"),
        ("LIVE", "Live"),
    )

    name = models.CharField(max_length=50)
    provider_type = models.CharField(max_length=10, choices=PROVIDER_TYPES)

    # e.g. https://wire-api.makylegacy.com (not required for YooPay)
    base_url = models.URLField(blank=True)

    # for MakyPay: api_key = public_key, api_secret = secret_key
    api_key = models.CharField(max_length=500)
    api_secret = models.CharField(max_length=500, blank=True)

    environment = models.CharField(
        max_length=10,
        choices=ENVIRONMENTS,
        default="SANDBOX"
    )

    # Only one provider should be active at a time
    is_active = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # ensure only one active provider at a time
        if self.is_active:
            PaymentProvider.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.environment})"


# =====================================================
# GLOBAL SYSTEM CONFIG (ONE ROW ONLY)
# =====================================================

class PaymentSystemConfig(models.Model):
    subscription_mode_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5,
        help_text="SpotPay commission % for MONTHLY SUBSCRIPTION locations (e.g. 5)"
    )
    percentage_mode_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15,
        help_text="SpotPay commission % for PERCENTAGE MODE locations (e.g. 15)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Commission Config"
        verbose_name_plural = "Commission Config"

    def save(self, *args, **kwargs):
        # enforce single row
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Commission: {self.subscription_mode_percentage}% (subscription) / {self.percentage_mode_percentage}% (percentage mode)"


# =====================================================
# PAYMENT (SINGLE SOURCE OF TRUTH)
# =====================================================

class Payment(models.Model):
    PURPOSES = (
        ("SUBSCRIPTION", "Location Subscription"),
        ("TRANSACTION", "Client Internet Purchase"),   # hotspot end-user purchase
        ("SMS_PURCHASE", "SMS Purchase"),
    )

    PAYER_TYPES = (
        ("VENDOR", "Vendor"),
        ("CLIENT", "Client"),
    )

    STATUSES = (
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    payer_type = models.CharField(max_length=10, choices=PAYER_TYPES)
    purpose = models.CharField(max_length=20, choices=PURPOSES)

    # ---- Who/Where (your existing links) ----
    vendor = models.ForeignKey(
        "accounts.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    location = models.ForeignKey(
        "hotspot.HotspotLocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # =================================================
    # HOTSPOT PURCHASE DETAILS
    # =================================================
    # payer phone number (MTN/Airtel)
    phone = models.CharField(max_length=20, null=True, blank=True)

    # package / plan purchased
    package = models.ForeignKey(
        "packages.Package",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # optional but useful for hotspot flows
    mac_address = models.CharField(max_length=32, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # =================================================
    # MONEY
    # =================================================
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="UGX")

    # =================================================
    # PROVIDER / GATEWAY TRACKING
    # =================================================
    provider = models.ForeignKey(
        PaymentProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # The "reference" returned by MakyPay request-to-pay
    # and later sent back in webhook
    provider_reference = models.CharField(
        max_length=500,
        unique=True,
        null=True,
        blank=True
    )

    external_reference = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    processor_message = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=STATUSES,
        default="PENDING"
    )

    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Save raw webhook data for audit/debugging
    raw_callback_data = models.JSONField(null=True, blank=True)

    # =================================================
    # HELPERS (IDEMPOTENT)
    # =================================================
    def mark_success(self, data=None):
        if self.status == "SUCCESS":
            return
        self.status = "SUCCESS"
        self.completed_at = timezone.now()
        if data is not None:
            self.raw_callback_data = data
        self.save(update_fields=["status", "completed_at", "raw_callback_data"])

    def mark_failed(self, data=None):
        if self.status == "FAILED":
            return
        self.status = "FAILED"
        if data is not None:
            self.raw_callback_data = data
        self.save(update_fields=["status", "raw_callback_data"])

    def __str__(self):
        return f"{self.purpose} | {self.amount} {self.currency} | {self.status}"


# =====================================================
# TRANSACTION SPLIT (AUDIT SAFE)
# =====================================================

class PaymentSplit(models.Model):
    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="split"
    )

    subscription_mode = models.CharField(max_length=20, default="MONTHLY")  # MONTHLY or PERCENTAGE
    spotpay_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    spotpay_amount = models.DecimalField(max_digits=12, decimal_places=2)
    vendor_amount = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Split {self.payment.uuid} | SpotPay {self.spotpay_percentage}% = {self.spotpay_amount} UGX"


# =====================================================
# VOUCHER ASSIGNMENT (RECOMMENDED FOR HOTSPOT)
# =====================================================
# Guarantees:
# - One payment -> one voucher
# - prevents issuing multiple vouchers if webhook retries
# - keeps auditing clean
class PaymentVoucher(models.Model):
    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="issued_voucher"
    )

    voucher = models.OneToOneField(
        "vouchers.Voucher",
        on_delete=models.PROTECT,
        related_name="payment_voucher"
    )

    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payment.uuid} -> {self.voucher}"

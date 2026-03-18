import uuid
from django.db import models
from accounts.models import Vendor
from hotspot.models import HotspotLocation


class RouterConnection(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="routers")
    location = models.OneToOneField(
        HotspotLocation, on_delete=models.CASCADE,
        related_name="router", null=True, blank=True
    )
    name = models.CharField(max_length=100, help_text="Friendly name e.g. Main Router")
    host = models.CharField(max_length=255, help_text="IP or hostname of the router")
    port = models.PositiveIntegerField(default=80)
    api_username = models.CharField(max_length=100, default="admin")
    api_password = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.host})"


class VoucherProfile(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="voucher_profiles")
    router = models.ForeignKey(RouterConnection, on_delete=models.CASCADE, related_name="profiles")
    name = models.CharField(max_length=100, help_text="Profile name as it appears on MikroTik")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    validity_hours = models.PositiveIntegerField(default=24, help_text="Hours of uptime allowed")
    data_limit_mb = models.PositiveIntegerField(
        null=True, blank=True, help_text="Data cap in MB (leave blank for unlimited)"
    )
    shared_users = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} — UGX {self.price}"


class VoucherBatch(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="mikrotik_batches")
    router = models.ForeignKey(RouterConnection, on_delete=models.CASCADE, related_name="batches")
    profile = models.ForeignKey(VoucherProfile, on_delete=models.CASCADE, related_name="batches")
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Batch {self.uuid} — {self.quantity} vouchers"


class MikrotikVoucher(models.Model):
    STATUS_UNUSED = "UNUSED"
    STATUS_USED = "USED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_CHOICES = [
        (STATUS_UNUSED, "Unused"),
        (STATUS_USED, "Used"),
        (STATUS_EXPIRED, "Expired"),
    ]

    batch = models.ForeignKey(VoucherBatch, on_delete=models.CASCADE, related_name="vouchers")
    code = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_UNUSED)
    pushed_to_router = models.BooleanField(default=False)
    push_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

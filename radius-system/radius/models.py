from django.db import models
from accounts.models import Vendor
import uuid
import random
import string


class NasDevice(models.Model):
    """MikroTik router registered to use this RADIUS server."""
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="nas_devices")
    name = models.CharField(max_length=100, help_text="Friendly name e.g. Main Router")
    nas_ip = models.GenericIPAddressField(help_text="MikroTik public/VPN IP")
    shared_secret = models.CharField(max_length=100, help_text="RADIUS shared secret")
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.nas_ip})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Sync to FreeRADIUS nas table
        from radius.freeradius import sync_nas
        sync_nas(self)


class Profile(models.Model):
    """Hotspot user profile — maps to FreeRADIUS group."""
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="profiles")
    name = models.CharField(max_length=100)
    # Time limit in minutes (0 = unlimited)
    session_timeout = models.PositiveIntegerField(default=0, help_text="Minutes (0 = unlimited)")
    # Data limit in MB (0 = unlimited)
    data_limit_mb = models.PositiveIntegerField(default=0, help_text="MB (0 = unlimited)")
    # Download/upload speed in Kbps (0 = unlimited)
    download_kbps = models.PositiveIntegerField(default=0, help_text="Kbps (0 = unlimited)")
    upload_kbps = models.PositiveIntegerField(default=0, help_text="Kbps (0 = unlimited)")
    # Shared users (simultaneous logins)
    simultaneous_use = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = [["vendor", "name"]]

    def __str__(self):
        return f"{self.name} ({self.vendor.company_name})"

    @property
    def session_timeout_display(self):
        if not self.session_timeout:
            return "Unlimited"
        h, m = divmod(self.session_timeout, 60)
        return f"{h}h {m}m" if h else f"{m}m"

    @property
    def data_limit_display(self):
        if not self.data_limit_mb:
            return "Unlimited"
        if self.data_limit_mb >= 1024:
            return f"{self.data_limit_mb / 1024:.1f} GB"
        return f"{self.data_limit_mb} MB"

    @property
    def speed_display(self):
        if not self.download_kbps:
            return "Unlimited"
        dl = f"{self.download_kbps // 1024} Mbps" if self.download_kbps >= 1024 else f"{self.download_kbps} Kbps"
        ul = f"{self.upload_kbps // 1024} Mbps" if self.upload_kbps >= 1024 else f"{self.upload_kbps} Kbps"
        return f"↓{dl} ↑{ul}"


class VoucherBatch(models.Model):
    """A batch of generated vouchers."""
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="voucher_batches")
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="batches")
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Batch {self.uuid} — {self.quantity} vouchers ({self.profile.name})"

    @property
    def unused_count(self):
        return self.vouchers.filter(status="UNUSED").count()

    @property
    def used_count(self):
        return self.vouchers.filter(status="USED").count()


class Voucher(models.Model):
    STATUS_UNUSED = "UNUSED"
    STATUS_USED = "USED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_DISABLED = "DISABLED"
    STATUS_CHOICES = [
        (STATUS_UNUSED, "Unused"),
        (STATUS_USED, "Used"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_DISABLED, "Disabled"),
    ]

    batch = models.ForeignKey(VoucherBatch, on_delete=models.CASCADE, related_name="vouchers")
    code = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_UNUSED)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    @staticmethod
    def generate_code(length=8):
        chars = string.ascii_uppercase + string.digits
        # Remove ambiguous characters
        chars = chars.replace("0", "").replace("O", "").replace("I", "").replace("1", "")
        return "".join(random.choices(chars, k=length))


class RadiusSession(models.Model):
    """Active/historical RADIUS accounting sessions — synced from FreeRADIUS."""
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="sessions")
    username = models.CharField(max_length=64)
    nas_ip = models.GenericIPAddressField()
    session_id = models.CharField(max_length=64, unique=True)
    framed_ip = models.GenericIPAddressField(null=True, blank=True)
    called_station_id = models.CharField(max_length=50, blank=True)
    calling_station_id = models.CharField(max_length=50, blank=True)
    # Bytes in/out
    bytes_in = models.BigIntegerField(default=0)
    bytes_out = models.BigIntegerField(default=0)
    session_time = models.PositiveIntegerField(default=0, help_text="Seconds")
    start_time = models.DateTimeField(null=True, blank=True)
    stop_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.username} — {self.nas_ip}"

    @property
    def data_used_display(self):
        total = self.bytes_in + self.bytes_out
        if total >= 1073741824:
            return f"{total / 1073741824:.2f} GB"
        if total >= 1048576:
            return f"{total / 1048576:.2f} MB"
        return f"{total / 1024:.1f} KB"

    @property
    def session_time_display(self):
        h, rem = divmod(self.session_time, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

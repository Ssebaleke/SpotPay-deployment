from django.db import models
from django.utils import timezone
from packages.models import Package


class Voucher(models.Model):
    STATUS_CHOICES = (
        ('UNUSED', 'Unused'),
        ('RESERVED', 'Reserved'),
        ('USED', 'Used'),
        ('EXPIRED', 'Expired'),
    )

    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name='vouchers'
    )

    # 🔑 ONE VOUCHER CODE
    code = models.CharField(max_length=100, unique=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='UNUSED'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def mark_used(self):
        self.status = 'USED'
        self.used_at = timezone.now()
        self.save(update_fields=['status', 'used_at'])

    def __str__(self):
        return f"{self.code} ({self.status})"

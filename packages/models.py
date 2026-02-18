from django.db import models
from hotspot.models import HotspotLocation


class Package(models.Model):
    location = models.ForeignKey(
        HotspotLocation,
        on_delete=models.CASCADE,
        related_name='packages'
    )
    name = models.CharField(max_length=100)
    price = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.name} - {self.location.site_name}"

    # ==================================================
    # VOUCHER LOGIC (CORE BUSINESS RULE)
    # ==================================================

    def available_vouchers_count(self):
        """
        Returns number of unused vouchers for this package
        """
        return self.voucher_set.filter(is_used=False).count()

    def has_vouchers(self):
        """
        Package is considered active ONLY if vouchers exist
        """
        return self.available_vouchers_count() > 0

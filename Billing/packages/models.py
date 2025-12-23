# packages/models.py
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

    def __str__(self):
        return f"{self.name} - {self.location.site_name}"

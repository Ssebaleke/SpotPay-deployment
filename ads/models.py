from django.db import models
from hotspot.models import HotspotLocation


class Ad(models.Model):
    AD_TYPE_CHOICES = (
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
    )

    location = models.ForeignKey(
        HotspotLocation,
        on_delete=models.CASCADE,
        related_name='ads'
    )

    title = models.CharField(max_length=100, blank=True)
    ad_type = models.CharField(max_length=10, choices=AD_TYPE_CHOICES)
    file = models.FileField(upload_to='ads/')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ad_type} Ad - {self.location.site_name}"

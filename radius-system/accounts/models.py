from django.db import models
from django.contrib.auth.models import User


class Vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vendor")
    company_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    # SpotPay vendor ID for SSO linking
    spotpay_vendor_id = models.IntegerField(null=True, blank=True, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name

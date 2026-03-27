# accounts/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db.models import Sum
from decimal import Decimal

class Vendor(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Approval'),
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('REJECTED', 'Rejected'),
    )
    
    # Link to User
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor')
    
    # Business Info
    company_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)
    business_address = models.CharField(max_length=100)
    business_phone = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Enter a valid phone number like +255123456789"
            )
        ]
    )
    business_email = models.EmailField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_vendors')
    approved_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Notification Preferences
    sms_notifications_enabled = models.BooleanField(
        default=False,
        help_text="Send SMS to vendor on every customer purchase"
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.company_name} ({self.status})"
    
    def is_approved(self):
        return self.status == 'ACTIVE'
    
    @property
    def total_received(self):
        """Total amount received from successful payments (before commission)"""
        from payments.models import Payment
        return Payment.objects.filter(
            vendor=self,
            purpose="TRANSACTION",
            status="SUCCESS"
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    
    @property
    def wallet_balance(self):
        """Current wallet balance"""
        try:
            return self.wallet.balance
        except:
            return Decimal("0.00")
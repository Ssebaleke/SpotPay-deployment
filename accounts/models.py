# accounts/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

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
    
    # Financial
    sms_balance = models.PositiveIntegerField(default=0)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.company_name} ({self.status})"
    
    def is_approved(self):
        return self.status == 'ACTIVE'
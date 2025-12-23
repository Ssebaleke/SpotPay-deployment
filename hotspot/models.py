# hotspot/models.py
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from accounts.models import Vendor
import uuid


class HotspotLocation(models.Model):
    """
    Represents a physical hotspot location.
    Each location has a UNIQUE, UNGUESSABLE UUID
    used for captive portal access.
    """

    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('ACTIVE', 'Active'),
        ('REJECTED', 'Rejected'),
        ('SUSPENDED', 'Suspended'),
    ]

    LOCATION_TYPES = [
        ('CAFE', 'Cafe / Restaurant'),
        ('HOTEL', 'Hotel / Lodge'),
        ('HOSTEL', 'Student Hostel'),
        ('APARTMENT', 'Apartment Building'),
        ('OFFICE', 'Office / Co-working'),
        ('PUBLIC', 'Public Space'),
        ('OTHER', 'Other'),
    ]

    # ============================
    # CORE RELATION
    # ============================

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='locations'
    )

    site_name = models.CharField(max_length=255)
    location_type = models.CharField(
        max_length=20,
        choices=LOCATION_TYPES,
        default='CAFE'
    )
    address = models.TextField()
    town_city = models.CharField(max_length=100)

    # ============================
    # SECURE PUBLIC IDENTIFIER
    # ============================

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    # Human-readable identifier (admin / UI only)
    location_slug = models.SlugField(
        max_length=80,
        unique=True,
        blank=True
    )

    # ============================
    # STATUS & APPROVAL
    # ============================

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_hotspot_locations'
    )

    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    admin_notes = models.TextField(
        blank=True,
        help_text="Internal notes (admin only)"
    )

    # ============================
    # PORTAL CONFIGURATION
    # ============================

    portal_url = models.URLField(blank=True)
    max_concurrent_users = models.PositiveIntegerField(default=50)
    is_active = models.BooleanField(default=True)

    # ============================
    # TIMESTAMPS
    # ============================

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Hotspot Location'
        verbose_name_plural = 'Hotspot Locations'

    def __str__(self):
        return f"{self.site_name} ({self.get_status_display()})"

    # ============================
    # SAVE LOGIC
    # ============================

    def save(self, *args, **kwargs):
        # Generate slug if missing (ADMIN / UI USE ONLY)
        if not self.location_slug:
            base_slug = slugify(f"{self.vendor.company_name}-{self.site_name}")[:60]
            slug = base_slug
            counter = 1

            while HotspotLocation.objects.filter(location_slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.location_slug = slug

        # Generate portal URL ONLY when ACTIVE
        if self.status == 'ACTIVE' and not self.portal_url:
            self.portal_url = f"https://portal.spotpay.com/portal/{self.uuid}/"

        super().save(*args, **kwargs)

    # ============================
    # STATUS ACTIONS
    # ============================

    def approve(self, admin_user):
        self.status = 'ACTIVE'
        self.approved_by = admin_user
        self.approved_at = timezone.now()
        self.rejection_reason = ''
        self.portal_url = f"http://127.0.0.1:8000/api/portal/{self.uuid}/"
        self.save()
        return True

    def reject(self, reason):
        self.status = 'REJECTED'
        self.rejection_reason = reason
        self.save()
        return True

    def suspend(self, reason=None):
        self.status = 'SUSPENDED'
        if reason:
            self.rejection_reason = reason
        self.save()
        return True

    # ============================
    # STATUS HELPERS
    # ============================

    def is_approved(self):
        return self.status == 'ACTIVE'

    def is_pending(self):
        return self.status == 'PENDING'

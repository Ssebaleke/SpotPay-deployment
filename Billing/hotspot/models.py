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

    # ============================
    # CHOICES
    # ============================

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

    SUBSCRIPTION_MODES = [
        ("MONTHLY", "Monthly Subscription"),
        ("PERCENTAGE", "Percentage Based"),
    ]

    # ============================
    # CORE RELATION
    # ============================

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name="locations"
    )

    site_name = models.CharField(max_length=255)
    location_type = models.CharField(
        max_length=20,
        choices=LOCATION_TYPES,
        default="CAFE"
    )
    address = models.TextField()
    town_city = models.CharField(max_length=100)

    # ============================
    # HOTSPOT LOGIN (MIKROTIK)
    # ============================

    hotspot_dns = models.CharField(
        max_length=100,
        default="hot.spot",
        help_text="DNS configured on MikroTik hotspot (e.g. hot.spot, wifi.shop.com)"
    )

    # ============================
    # SUBSCRIPTION (PER LOCATION)
    # ============================

    subscription_mode = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_MODES,
        default="MONTHLY"
    )

    subscription_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Revenue share percentage (used only in percentage mode)"
    )

    subscription_active = models.BooleanField(default=False)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)

    # ============================
    # SECURE PUBLIC IDENTIFIER
    # ============================

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

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
        default="PENDING"
    )

    approved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_hotspot_locations"
    )

    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    admin_notes = models.TextField(
        blank=True,
        help_text="Internal admin notes"
    )

    # ============================
    # PORTAL CONFIGURATION
    # ============================

    portal_url = models.URLField(
        blank=True,
        help_text="Django captive portal URL"
    )

    max_concurrent_users = models.PositiveIntegerField(default=50)
    is_active = models.BooleanField(default=False)

    # ============================
    # TIMESTAMPS
    # ============================

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Hotspot Location"
        verbose_name_plural = "Hotspot Locations"

    def __str__(self):
        return f"{self.site_name} ({self.get_status_display()})"

    # ============================
    # SAVE LOGIC
    # ============================

    def save(self, *args, **kwargs):
        """
        Central enforcement of subscription rules
        """

        # Percentage mode is ALWAYS active
        if self.subscription_mode == "PERCENTAGE":
            self.subscription_active = True
            self.subscription_expires_at = None
            self.is_active = True

        # Generate slug once
        if not self.location_slug:
            base_slug = slugify(f"{self.vendor.company_name}-{self.site_name}")[:60]
            slug = base_slug
            counter = 1

            while HotspotLocation.objects.filter(location_slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.location_slug = slug

        # Generate portal URL once approved
        if self.status == "ACTIVE" and not self.portal_url:
            self.portal_url = f"http://127.0.0.1:8000/api/portal/{self.uuid}/"

        super().save(*args, **kwargs)

    # ============================
    # STATUS ACTIONS
    # ============================

    def approve(self, admin_user):
        self.status = "ACTIVE"
        self.approved_by = admin_user
        self.approved_at = timezone.now()
        self.rejection_reason = ""
        self.is_active = True
        self.save()
        return True

    def reject(self, reason):
        self.status = "REJECTED"
        self.rejection_reason = reason
        self.is_active = False
        self.save()
        return True

    def suspend(self, reason=None):
        self.status = "SUSPENDED"
        if reason:
            self.rejection_reason = reason
        self.is_active = False
        self.save()
        return True

    # ============================
    # SUBSCRIPTION CHECK (CRITICAL)
    # ============================

    def has_active_subscription(self):
        """
        Single source of truth for service access.
        Used everywhere (portal, APIs, payments).
        """

        # Percentage-based locations are always allowed
        if self.subscription_mode == "PERCENTAGE":
            return True

        if not self.subscription_active:
            return False

        if self.subscription_expires_at:
            return self.subscription_expires_at > timezone.now()

        return True

from django.db import models
from django.utils import timezone
from hotspot.models import HotspotLocation


class Package(models.Model):

    SCHEDULE_TYPES = [
        ('ALWAYS', 'Always Available'),
        ('WEEKDAYS', 'Specific Days of the Week'),
        ('DATE', 'Specific Date'),
    ]

    DAY_CHOICES = [
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ]

    location = models.ForeignKey(
        HotspotLocation,
        on_delete=models.CASCADE,
        related_name='packages'
    )
    name = models.CharField(max_length=100)
    price = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    # ── Scheduling ──────────────────────────────────
    schedule_type = models.CharField(
        max_length=10,
        choices=SCHEDULE_TYPES,
        default='ALWAYS'
    )
    # Comma-separated weekday numbers e.g. "4" = Friday, "4,5" = Fri+Sat
    scheduled_days = models.CharField(
        max_length=20,
        blank=True,
        help_text='Comma-separated weekday numbers (0=Mon … 6=Sun)'
    )
    # Specific calendar date e.g. public holiday
    scheduled_date = models.DateField(null=True, blank=True)
    # Optional time window within the day
    scheduled_start = models.TimeField(null=True, blank=True)
    scheduled_end = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.name} - {self.location.site_name}"

    def is_available_now(self):
        """Returns True if this package should be shown right now."""
        if not self.is_active:
            return False
        if self.schedule_type == 'ALWAYS':
            return True

        now = timezone.localtime(timezone.now())
        today = now.date()
        current_time = now.time()

        if self.schedule_type == 'DATE':
            if self.scheduled_date != today:
                return False

        elif self.schedule_type == 'WEEKDAYS':
            allowed = [d.strip() for d in (self.scheduled_days or '').split(',') if d.strip()]
            if str(today.weekday()) not in allowed:
                return False

        # Optional time window check (applies to both WEEKDAYS and DATE)
        if self.scheduled_start and current_time < self.scheduled_start:
            return False
        if self.scheduled_end and current_time > self.scheduled_end:
            return False

        return True

    def available_vouchers_count(self):
        return self.vouchers.filter(status='UNUSED').count()

    def has_vouchers(self):
        return self.available_vouchers_count() > 0

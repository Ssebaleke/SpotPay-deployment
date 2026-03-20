from django.core.management.base import BaseCommand
from django.utils import timezone
from hotspot.models import HotspotLocation
from sms.services.notifications import notify_subscription_expiry


class Command(BaseCommand):
    help = "Enforce hotspot subscription expiry and warnings"

    def handle(self, *args, **options):
        now = timezone.now()

        locations = HotspotLocation.objects.filter(
            subscription_mode="MONTHLY"
        ).select_related("vendor", "vendor__user")

        for location in locations:

            if not location.subscription_expires_at:
                continue

            days_left = (location.subscription_expires_at.date() - now.date()).days

            # EXPIRED
            if days_left < 0:
                if location.is_active:
                    location.subscription_active = False
                    location.is_active = False
                    location.save()
                    notify_subscription_expiry(location, days_left)
                    self.stdout.write(self.style.ERROR(
                        f"{location.site_name}: expired → deactivated, vendor notified"
                    ))

            # EXPIRING SOON — warn at 3, 2, 1 days
            elif days_left <= 3:
                notify_subscription_expiry(location, days_left)
                self.stdout.write(self.style.WARNING(
                    f"{location.site_name}: expires in {days_left} day(s), vendor notified"
                ))

        self.stdout.write(self.style.SUCCESS("Subscription enforcement completed"))

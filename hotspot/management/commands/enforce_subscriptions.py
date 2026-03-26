from django.core.management.base import BaseCommand
from django.utils import timezone
from hotspot.models import HotspotLocation
from sms.services.notifications import notify_subscription_expiry


class Command(BaseCommand):
    help = "Enforce hotspot subscription expiry and send warning emails"

    def handle(self, *args, **options):
        now = timezone.now()

        locations = HotspotLocation.objects.filter(
            subscription_mode="MONTHLY"
        ).select_related("vendor", "vendor__user")

        for location in locations:

            if not location.subscription_expires_at:
                continue

            days_left = (location.subscription_expires_at.date() - now.date()).days

            # EXPIRED — deactivate and notify once (when is_active flips)
            if days_left < 0:
                if location.is_active or location.subscription_active:
                    location.subscription_active = False
                    location.is_active = False
                    location.save(update_fields=['subscription_active', 'is_active', 'updated_at'])
                    try:
                        notify_subscription_expiry(location, days_left)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(
                            f"Email failed for {location.site_name}: {e}"
                        ))
                    self.stdout.write(self.style.ERROR(
                        f"{location.site_name}: EXPIRED — deactivated, vendor notified"
                    ))

            # EXPIRING SOON — warn only at exactly 3, 2, 1 days to avoid daily spam
            elif days_left in (1, 2, 3):
                try:
                    notify_subscription_expiry(location, days_left)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f"Warning email failed for {location.site_name}: {e}"
                    ))
                self.stdout.write(self.style.WARNING(
                    f"{location.site_name}: expires in {days_left} day(s) — vendor warned"
                ))

        self.stdout.write(self.style.SUCCESS("Subscription enforcement completed"))

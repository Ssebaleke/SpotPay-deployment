from django.core.management.base import BaseCommand
from django.utils import timezone
from hotspot.models import HotspotLocation


class Command(BaseCommand):
    help = "Enforce hotspot subscription expiry and warnings"

    def handle(self, *args, **options):
        now = timezone.now()

        locations = HotspotLocation.objects.filter(
            subscription_mode="MONTHLY"
        )

        for location in locations:

            # Skip locations that were never activated
            if not location.subscription_expires_at:
                continue

            days_left = (location.subscription_expires_at.date() - now.date()).days

            # 🔴 EXPIRED
            if days_left < 0:
                if location.is_active:
                    location.subscription_active = False
                    location.is_active = False
                    location.save()

                    self.stdout.write(
                        self.style.ERROR(
                            f"{location.site_name}: subscription expired → deactivated"
                        )
                    )

            # 🟡 EXPIRING SOON (WARNINGS ONLY)
            elif days_left <= 3:
                self.stdout.write(
                    self.style.WARNING(
                        f"{location.site_name}: expires in {days_left} day(s)"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Subscription enforcement completed"))

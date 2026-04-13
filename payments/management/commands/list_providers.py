from django.core.management.base import BaseCommand
from payments.models import PaymentProvider

class Command(BaseCommand):
    help = 'List all payment providers in database'

    def handle(self, *args, **options):
        self.stdout.write("All Payment Providers in Database:")
        self.stdout.write("=" * 40)
        
        providers = PaymentProvider.objects.all()
        
        if not providers.exists():
            self.stdout.write("NO payment providers found in database!")
            return
        
        for provider in providers:
            status = "ACTIVE" if provider.is_active else "INACTIVE"
            self.stdout.write(f"ID: {provider.id}")
            self.stdout.write(f"Name: {provider.name}")
            self.stdout.write(f"Type: {provider.provider_type}")
            self.stdout.write(f"Environment: {provider.environment}")
            self.stdout.write(f"Status: {status}")
            self.stdout.write(f"API Key: {provider.api_key[:10]}...")
            self.stdout.write(f"API Secret: {provider.api_secret[:10]}...")
            self.stdout.write("-" * 40)
        
        self.stdout.write(f"\nTotal providers: {providers.count()}")
        active_count = providers.filter(is_active=True).count()
        self.stdout.write(f"Active providers: {active_count}")
from django.core.management.base import BaseCommand
from payments.models import PaymentProvider

class Command(BaseCommand):
    help = 'Add LivePay provider to database'

    def handle(self, *args, **options):
        self.stdout.write("Adding LivePay provider...")
        
        # Check if LivePay provider already exists
        existing = PaymentProvider.objects.filter(provider_type="LIVE").first()
        if existing:
            self.stdout.write(f"LivePay provider already exists: {existing.name}")
            return
        
        # Create LivePay provider
        provider = PaymentProvider.objects.create(
            name="LivePay Uganda",
            provider_type="LIVE",
            base_url="",  # Not needed for LivePay
            api_key="89b4e8e5858ada4e",
            api_secret="39eacb226cb2466f16c243bab671897ba3288f9b82a1639ff8e0df9df2503c96",
            transaction_pin="",  # Not needed
            environment="LIVE",
            is_active=True,
            gateway_fee_percentage=2.0
        )
        
        self.stdout.write(self.style.SUCCESS("LivePay provider created successfully!"))
        self.stdout.write(f"ID: {provider.id}")
        self.stdout.write(f"Name: {provider.name}")
        self.stdout.write(f"Type: {provider.provider_type}")
        self.stdout.write(f"Active: {provider.is_active}")
        
        # Test the provider
        self.stdout.write("\nTesting LivePay client...")
        try:
            from payments.live_client import LivePayClient
            client = LivePayClient(
                public_key=provider.api_key,
                secret_key=provider.api_secret
            )
            self.stdout.write(self.style.SUCCESS("LivePay client initialized successfully"))
            
            # Test API call
            result = client.collect(
                amount=1000,
                phone="256700000000", 
                reference="SETUP_TEST",
                description="Setup test"
            )
            
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS("LivePay API test successful!"))
            else:
                self.stdout.write(self.style.WARNING(f"LivePay API response: {result.get('message', 'Unknown')}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"LivePay test failed: {e}"))
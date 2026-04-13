from django.core.management.base import BaseCommand
from payments.models import PaymentProvider
from payments.live_client import LivePayClient
import json

class Command(BaseCommand):
    help = 'Update LivePay provider with correct API key'

    def handle(self, *args, **options):
        key_id = "89b4e8e5858ada4e"
        new_api_key = "59acc6e62303bef3.6cb258aace07e21de83cfa6c0e84364332ac1b0782fcb9e524e727e46ec064b9"
        
        self.stdout.write("Updating LivePay provider with correct API key...")
        
        # Update the provider
        provider = PaymentProvider.objects.filter(provider_type="LIVE").first()
        if not provider:
            self.stdout.write("No LivePay provider found!")
            return
        
        provider.api_key = key_id
        provider.api_secret = new_api_key
        provider.save()
        
        self.stdout.write(f"Updated provider: {provider.name}")
        self.stdout.write(f"API Key: {provider.api_key}")
        self.stdout.write(f"API Secret: {provider.api_secret[:20]}...")
        
        # Test the updated credentials
        self.stdout.write("\nTesting updated credentials...")
        try:
            client = LivePayClient(
                public_key=provider.api_key,
                secret_key=provider.api_secret
            )
            
            result = client.collect(
                amount=1000,
                phone="256700000000",
                reference="UPDATED_TEST",
                description="Test with updated credentials"
            )
            
            self.stdout.write(f"API Response: {json.dumps(result, indent=2)}")
            
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS("SUCCESS! LivePay API is now working!"))
            else:
                self.stdout.write(f"API Error: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            self.stdout.write(f"Test failed: {e}")
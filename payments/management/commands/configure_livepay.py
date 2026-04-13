from django.core.management.base import BaseCommand
from payments.models import PaymentProvider
from payments.live_client import LivePayClient
import json

class Command(BaseCommand):
    help = 'Configure LivePay with proper credentials including webhook secret'

    def handle(self, *args, **options):
        self.stdout.write("Configuring LivePay with proper credentials...")
        
        # LivePay credentials
        account_number = "89b4e8e5858ada4e"  # Key ID from dashboard
        api_key = "59acc6e62303bef3.6cb258aace07e21de83cfa6c0e84364332ac1b0782fcb9e524e727e46ec064b9"  # Full API key
        webhook_secret = ""  # Will be provided by user
        
        self.stdout.write("\\nLivePay Credential Mapping:")
        self.stdout.write("=" * 40)
        self.stdout.write("Account Number (api_key field): " + account_number)
        self.stdout.write("API Key (api_secret field): " + api_key[:30] + "...")
        self.stdout.write("Webhook Secret (webhook_secret field): [TO BE PROVIDED]")
        
        # Update or create LivePay provider
        provider, created = PaymentProvider.objects.get_or_create(
            provider_type="LIVE",
            defaults={
                "name": "LivePay Uganda",
                "base_url": "",
                "api_key": account_number,
                "api_secret": api_key,
                "webhook_secret": webhook_secret,
                "transaction_pin": "",
                "environment": "LIVE",
                "is_active": True,
                "gateway_fee_percentage": 2.0
            }
        )
        
        if not created:
            # Update existing provider
            provider.api_key = account_number
            provider.api_secret = api_key
            provider.webhook_secret = webhook_secret
            provider.is_active = True
            provider.save()
            self.stdout.write("Updated existing LivePay provider")
        else:
            self.stdout.write("Created new LivePay provider")
        
        # Test the API credentials
        self.stdout.write("\\nTesting LivePay API credentials...")
        try:
            client = LivePayClient(
                public_key=provider.api_key,
                secret_key=provider.api_secret
            )
            
            result = client.collect(
                amount=1000,
                phone="256700000000",
                reference="CONFIG_TEST",
                description="Configuration test"
            )
            
            self.stdout.write(f"API Response: {json.dumps(result, indent=2)}")
            
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS("SUCCESS! LivePay API is working!"))
            elif "Account number does not match" in result.get('message', ''):
                self.stdout.write(self.style.ERROR("Account number mismatch - need correct account number"))
            else:
                self.stdout.write(f"API Error: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            self.stdout.write(f"Test failed: {e}")
        
        self.stdout.write("\\n" + "=" * 60)
        self.stdout.write("NEXT STEPS:")
        self.stdout.write("=" * 60)
        self.stdout.write("1. Find your ACCOUNT NUMBER in LivePay dashboard (different from Key ID)")
        self.stdout.write("2. Generate WEBHOOK SECRET in LivePay dashboard")
        self.stdout.write("3. Update provider in Django Admin with:")
        self.stdout.write("   - API Key: [Your Account Number]")
        self.stdout.write("   - API Secret: " + api_key[:30] + "...")
        self.stdout.write("   - Webhook Secret: [Generated webhook secret]")
        self.stdout.write("4. Register webhook URL: https://spotpay.it.com/payments/webhook/live/ipn/")
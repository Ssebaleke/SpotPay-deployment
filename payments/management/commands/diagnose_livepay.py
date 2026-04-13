from django.core.management.base import BaseCommand
from payments.models import PaymentProvider, Payment
from payments.live_client import LivePayClient
import json

class Command(BaseCommand):
    help = 'Diagnose LivePay integration issues'

    def handle(self, *args, **options):
        self.stdout.write("LivePay Integration Diagnostic")
        self.stdout.write("=" * 50)
        
        # Check PaymentProvider configuration
        self.stdout.write("\n1. Checking PaymentProvider configuration...")
        
        live_providers = PaymentProvider.objects.filter(provider_type="LIVE")
        
        if not live_providers.exists():
            self.stdout.write(self.style.ERROR("NO LivePay provider found in database!"))
            self.stdout.write("SOLUTION: Go to Django Admin -> Payment Providers -> Add Payment Provider")
            self.stdout.write("Set Provider Type to 'Mobile Money (LivePay)'")
            return
        
        active_live = live_providers.filter(is_active=True).first()
        if not active_live:
            self.stdout.write(self.style.ERROR("LivePay provider exists but is NOT ACTIVE!"))
            for provider in live_providers:
                status = "ACTIVE" if provider.is_active else "INACTIVE"
                self.stdout.write(f"Found: {provider.name} ({status})")
            self.stdout.write("SOLUTION: Go to Django Admin and set LivePay provider as Active")
            return
        
        self.stdout.write(self.style.SUCCESS(f"Active LivePay provider: {active_live.name}"))
        self.stdout.write(f"API Key: {active_live.api_key[:10]}...")
        self.stdout.write(f"API Secret: {active_live.api_secret[:10]}...")
        self.stdout.write(f"Environment: {active_live.environment}")
        
        # Test LivePay client
        self.stdout.write("\n2. Testing LivePay client...")
        try:
            client = LivePayClient(
                public_key=active_live.api_key,
                secret_key=active_live.api_secret
            )
            self.stdout.write(self.style.SUCCESS("LivePay client initialized successfully"))
            
            # Test API call
            self.stdout.write("3. Testing LivePay API...")
            result = client.collect(
                amount=1000,
                phone="256700000000",
                reference="TEST123",
                description="Test payment"
            )
            
            self.stdout.write(f"API Response: {json.dumps(result, indent=2)}")
            
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS("LivePay API is working!"))
            else:
                self.stdout.write(self.style.ERROR(f"LivePay API rejected: {result.get('message', 'Unknown error')}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"LivePay client/API error: {e}"))
        
        # Check other active providers
        self.stdout.write("\n4. Checking other payment providers...")
        other_active = PaymentProvider.objects.filter(is_active=True).exclude(provider_type="LIVE")
        if other_active.exists():
            self.stdout.write(self.style.WARNING("Other active providers found:"))
            for provider in other_active:
                self.stdout.write(f"  {provider.name} ({provider.provider_type}) - ACTIVE")
            self.stdout.write("WARNING: Only ONE provider should be active at a time!")
        else:
            self.stdout.write(self.style.SUCCESS("No conflicting active providers"))
        
        # Check recent payments
        self.stdout.write("\n5. Recent payments...")
        recent_payments = Payment.objects.filter(provider=active_live).order_by('-initiated_at')[:5]
        
        if recent_payments.exists():
            self.stdout.write("Recent LivePay payments:")
            for payment in recent_payments:
                self.stdout.write(f"  {payment.uuid} | {payment.status} | {payment.amount} UGX | {payment.initiated_at}")
        else:
            self.stdout.write("No recent LivePay payments found")
        
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("SUMMARY:")
        self.stdout.write("If no issues found above, LivePay should be working.")
        self.stdout.write("If payments still fail, check:")
        self.stdout.write("1. Phone number format (256XXXXXXXXX)")
        self.stdout.write("2. Webhook URL registered in LivePay dashboard")
        self.stdout.write("3. Your hotspot portal payment flow")
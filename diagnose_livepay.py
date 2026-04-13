#!/usr/bin/env python
"""
LivePay Integration Diagnostic Tool
==================================
This script will identify exactly what's wrong with LivePay integration.
"""

import os
import sys
import django
import json
from datetime import datetime

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Billing.settings')

try:
    django.setup()
    print("✅ Django setup successful")
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    print("💡 Try: python manage.py shell instead")
    sys.exit(1)

def check_database():
    """Check if database is accessible"""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def check_payment_providers():
    """Check PaymentProvider configuration"""
    try:
        from payments.models import PaymentProvider
        
        print("\n📋 Payment Providers in Database:")
        providers = PaymentProvider.objects.all()
        
        if not providers.exists():
            print("❌ NO payment providers found in database!")
            print("   → You need to add LivePay provider through Django Admin")
            return False
        
        active_count = 0
        livepay_found = False
        livepay_active = False
        
        for provider in providers:
            status = "🟢 ACTIVE" if provider.is_active else "🔴 INACTIVE"
            print(f"   → {provider.name} ({provider.provider_type}) - {status}")
            
            if provider.is_active:
                active_count += 1
            
            if provider.provider_type == "LIVE":
                livepay_found = True
                if provider.is_active:
                    livepay_active = True
                    print(f"     API Key: {provider.api_key[:10]}...")
                    print(f"     API Secret: {provider.api_secret[:10]}...")
        
        if not livepay_found:
            print("❌ LivePay provider NOT FOUND!")
            print("   → Add LivePay provider in Django Admin")
            return False
        
        if not livepay_active:
            print("❌ LivePay provider found but NOT ACTIVE!")
            print("   → Activate LivePay provider in Django Admin")
            return False
        
        if active_count > 1:
            print(f"⚠️  Multiple providers active ({active_count})!")
            print("   → Only one provider should be active at a time")
        
        print("✅ LivePay provider is active and configured")
        return True
        
    except Exception as e:
        print(f"❌ Error checking payment providers: {e}")
        return False

def test_livepay_client():
    """Test LivePay client initialization and API call"""
    try:
        from payments.models import PaymentProvider
        from payments.live_client import LivePayClient
        
        provider = PaymentProvider.objects.filter(provider_type="LIVE", is_active=True).first()
        if not provider:
            print("❌ No active LivePay provider found")
            return False
        
        print(f"\n🔧 Testing LivePay Client with provider: {provider.name}")
        
        # Test client initialization
        try:
            client = LivePayClient(
                public_key=provider.api_key,
                secret_key=provider.api_secret
            )
            print("✅ LivePay client initialized successfully")
        except Exception as e:
            print(f"❌ LivePay client initialization failed: {e}")
            return False
        
        # Test API call
        print("🌐 Testing LivePay API connection...")
        try:
            result = client.collect(
                amount=1000,
                phone="256700000000",
                reference="DIAGNOSTIC_TEST",
                description="Diagnostic test"
            )
            
            print(f"📡 API Response: {json.dumps(result, indent=2)}")
            
            if result.get('success'):
                print("✅ LivePay API is working!")
                return True
            else:
                print(f"❌ LivePay API rejected request: {result.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ LivePay API call failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing LivePay client: {e}")
        return False

def check_recent_payments():
    """Check recent payment attempts"""
    try:
        from payments.models import Payment
        
        print("\n💳 Recent Payment Attempts (last 10):")
        recent_payments = Payment.objects.all().order_by('-initiated_at')[:10]
        
        if not recent_payments.exists():
            print("📭 No payments found in database")
            return
        
        for payment in recent_payments:
            provider_name = payment.provider.name if payment.provider else "No Provider"
            print(f"   → {payment.uuid} | {payment.status} | {payment.amount} UGX | {provider_name} | {payment.initiated_at}")
        
        # Check for LivePay payments specifically
        livepay_payments = Payment.objects.filter(provider__provider_type="LIVE").order_by('-initiated_at')[:5]
        if livepay_payments.exists():
            print("\n💰 Recent LivePay Payments:")
            for payment in livepay_payments:
                print(f"   → {payment.uuid} | {payment.status} | {payment.phone} | {payment.initiated_at}")
        else:
            print("\n📭 No LivePay payments found")
            
    except Exception as e:
        print(f"❌ Error checking payments: {e}")

def check_environment_variables():
    """Check environment variables"""
    print("\n🌍 Environment Variables:")
    
    env_vars = [
        'LIVEPAY_PUBLIC_KEY',
        'LIVEPAY_SECRET_KEY', 
        'SITE_URL',
        'DEBUG'
    ]
    
    for var in env_vars:
        value = os.getenv(var, 'NOT SET')
        if var.endswith('_KEY') and value != 'NOT SET':
            value = value[:10] + "..."
        print(f"   → {var}: {value}")

def check_urls_and_webhooks():
    """Check URL configuration"""
    try:
        from django.conf import settings
        
        print(f"\n🔗 URL Configuration:")
        print(f"   → SITE_URL: {settings.SITE_URL}")
        print(f"   → LivePay Webhook: {settings.SITE_URL}/payments/webhook/live/ipn/")
        
        # Test URL patterns
        from django.urls import reverse
        try:
            live_ipn_url = reverse('payments:live_ipn')
            print(f"   → Live IPN URL pattern: {live_ipn_url}")
        except Exception as e:
            print(f"   → Live IPN URL pattern error: {e}")
            
    except Exception as e:
        print(f"❌ Error checking URLs: {e}")

def main():
    print("🔍 LivePay Integration Diagnostic")
    print("=" * 60)
    print(f"Timestamp: {datetime.now()}")
    print("=" * 60)
    
    # Run all checks
    db_ok = check_database()
    if not db_ok:
        print("\n❌ Database issues found. Fix database connection first.")
        return
    
    providers_ok = check_payment_providers()
    client_ok = test_livepay_client() if providers_ok else False
    
    check_recent_payments()
    check_environment_variables()
    check_urls_and_webhooks()
    
    print("\n" + "=" * 60)
    print("🎯 DIAGNOSIS SUMMARY:")
    print("=" * 60)
    
    if not providers_ok:
        print("❌ MAIN ISSUE: LivePay provider not configured or not active")
        print("   SOLUTION: Go to Django Admin → Payment Providers")
        print("   1. Add new PaymentProvider with type 'Mobile Money (LivePay)'")
        print("   2. Set API Key: 89b4e8e5858ada4e")
        print("   3. Set API Secret: 39eacb226cb2466f16c243bab671897ba3288f9b82a1639ff8e0df9df2503c96")
        print("   4. Check 'Is Active' checkbox")
        print("   5. Save")
    elif not client_ok:
        print("❌ MAIN ISSUE: LivePay API connection problems")
        print("   SOLUTION: Check your API credentials with LivePay")
    else:
        print("✅ LivePay integration appears to be working!")
        print("   If payments still don't work, check:")
        print("   1. Your hotspot portal is using the correct payment flow")
        print("   2. Phone numbers are in correct format (256XXXXXXXXX)")
        print("   3. LivePay webhook URL is registered in LivePay dashboard")

if __name__ == "__main__":
    main()
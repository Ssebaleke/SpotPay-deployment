#!/usr/bin/env python
"""
Debug LivePay Integration
========================
This script helps diagnose LivePay integration issues.
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Billing.settings')
django.setup()

from payments.models import PaymentProvider
from payments.live_client import LivePayClient
import json

def main():
    print("🔍 LivePay Integration Debug")
    print("=" * 50)
    
    # 1. Check if LivePay provider exists and is active
    print("\n1. Checking PaymentProvider configuration...")
    live_providers = PaymentProvider.objects.filter(provider_type="LIVE")
    
    if not live_providers.exists():
        print("❌ No LivePay provider found in database!")
        print("   → Go to Django Admin → Payment Providers → Add Payment Provider")
        print("   → Set Provider Type to 'Mobile Money (LivePay)'")
        return
    
    active_live = live_providers.filter(is_active=True).first()
    if not active_live:
        print("❌ LivePay provider exists but is NOT ACTIVE!")
        for provider in live_providers:
            print(f"   → Found: {provider.name} (Active: {provider.is_active})")
        print("   → Go to Django Admin and set LivePay provider as Active")
        return
    
    print(f"✅ Active LivePay provider: {active_live.name}")
    print(f"   → API Key: {active_live.api_key[:10]}...")
    print(f"   → API Secret: {active_live.api_secret[:10]}...")
    print(f"   → Environment: {active_live.environment}")
    
    # 2. Test LivePay client initialization
    print("\n2. Testing LivePay client initialization...")
    try:
        client = LivePayClient(
            public_key=active_live.api_key,
            secret_key=active_live.api_secret
        )
        print("✅ LivePay client initialized successfully")
        print(f"   → Account Number: {client.account_number}")
        print(f"   → API Key: {client.api_key[:10]}...")
    except Exception as e:
        print(f"❌ Failed to initialize LivePay client: {e}")
        return
    
    # 3. Test a small collection request (won't actually charge)
    print("\n3. Testing LivePay collection API...")
    try:
        result = client.collect(
            amount=1000,  # 1000 UGX
            phone="256700000000",  # Test phone
            reference="TEST123",
            description="Test payment"
        )
        print("✅ LivePay API call successful")
        print(f"   → Response: {json.dumps(result, indent=2)}")
        
        if result.get('success'):
            print("✅ LivePay accepted the request")
        else:
            print(f"❌ LivePay rejected: {result.get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ LivePay API call failed: {e}")
    
    # 4. Check other active providers
    print("\n4. Checking other payment providers...")
    other_active = PaymentProvider.objects.filter(is_active=True).exclude(provider_type="LIVE")
    if other_active.exists():
        print("⚠️  Other active providers found:")
        for provider in other_active:
            print(f"   → {provider.name} ({provider.provider_type}) - ACTIVE")
        print("   → Only ONE provider should be active at a time!")
    else:
        print("✅ No conflicting active providers")
    
    # 5. Check recent payments
    print("\n5. Checking recent payments...")
    from payments.models import Payment
    recent_payments = Payment.objects.filter(provider=active_live).order_by('-initiated_at')[:5]
    
    if recent_payments.exists():
        print("📋 Recent LivePay payments:")
        for payment in recent_payments:
            print(f"   → {payment.uuid} | {payment.status} | {payment.amount} UGX | {payment.initiated_at}")
    else:
        print("📋 No recent LivePay payments found")
    
    print("\n" + "=" * 50)
    print("🎯 Next Steps:")
    print("1. If LivePay provider is missing → Add it in Django Admin")
    print("2. If LivePay is inactive → Activate it in Django Admin") 
    print("3. If API calls fail → Check your API credentials")
    print("4. If multiple providers active → Deactivate others")
    print("5. Test a real payment from your hotspot portal")

if __name__ == "__main__":
    main()
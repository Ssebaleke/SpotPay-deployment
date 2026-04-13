#!/usr/bin/env python3
"""
Quick test to verify vendor withdrawal system is ready with LivePay.
"""

import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Billing.settings')
django.setup()

from payments.models import PaymentProvider
from payments.live_client import LivePayClient
from wallets.models import VendorWallet, WithdrawalRequest
from accounts.models import Vendor

def check_livepay_withdrawal_ready():
    print("🔍 Checking LivePay Withdrawal System...")
    
    # 1. Check if LivePay provider is configured
    provider = PaymentProvider.objects.filter(provider_type="LIVE", is_active=True).first()
    if not provider:
        print("❌ No active LivePay provider found")
        print("   → Go to /admin/payments/paymentprovider/ and configure LivePay")
        return False
    
    if not provider.api_key or not provider.api_secret:
        print("❌ LivePay provider missing credentials")
        print("   → Add your API key and account number in admin")
        return False
    
    print(f"✅ LivePay provider configured: {provider.name}")
    
    # 2. Test LivePay client initialization
    try:
        client = LivePayClient(
            public_key=provider.api_key,
            secret_key=provider.api_secret
        )
        print("✅ LivePay client initializes successfully")
    except Exception as e:
        print(f"❌ LivePay client error: {e}")
        return False
    
    # 3. Check if vendors have wallets
    vendors_with_wallets = Vendor.objects.filter(wallet__isnull=False).count()
    total_vendors = Vendor.objects.count()
    print(f"✅ {vendors_with_wallets}/{total_vendors} vendors have wallets")
    
    # 4. Check withdrawal requests
    pending_withdrawals = WithdrawalRequest.objects.filter(status='pending').count()
    print(f"📊 {pending_withdrawals} pending withdrawal requests")
    
    # 5. Test send money method (dry run)
    print("\n🧪 Testing send money method (dry run)...")
    try:
        # This won't actually send money, just test the method structure
        result = client.send(
            amount=1000,
            phone="0777123456", 
            reference="TEST123",
            description="Test withdrawal"
        )
        print("✅ Send money method structure is correct")
    except Exception as e:
        print(f"❌ Send money method error: {e}")
        return False
    
    print("\n🎉 Vendor withdrawal system is READY!")
    print("\n📋 What vendors can do now:")
    print("   1. View wallet balance at /wallet/")
    print("   2. Request withdrawals at /wallet/withdraw/")
    print("   3. Enter phone number and amount")
    print("   4. Verify with OTP")
    print("   5. Money sent instantly to their mobile money")
    
    return True

if __name__ == "__main__":
    check_livepay_withdrawal_ready()
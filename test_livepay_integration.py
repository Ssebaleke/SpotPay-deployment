#!/usr/bin/env python3
"""
Test script for LivePay integration updates.
Run this to verify the LivePay client works with the new API endpoints.

Usage:
    python test_livepay_integration.py
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Billing.settings')
django.setup()

from payments.live_client import LivePayClient
from payments.models import PaymentProvider
import logging

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def test_livepay_client():
    """Test LivePay client with dummy credentials."""
    print("🧪 Testing LivePay Client Integration...")
    
    # Test with dummy credentials
    try:
        client = LivePayClient(
            public_key="LP2305443309",  # Dummy account number
            secret_key="dummy_api_key"   # Dummy API key
        )
        print("✅ LivePay client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize LivePay client: {e}")
        return False
    
    # Test phone normalization
    test_phones = [
        "0777123456",
        "+256777123456", 
        "256777123456",
        "777123456"
    ]
    
    print("\n📱 Testing phone number normalization:")
    for phone in test_phones:
        normalized = client._normalize_phone(phone)
        print(f"  {phone} → {normalized}")
    
    # Test network detection
    print("\n🌐 Testing network detection:")
    for phone in test_phones:
        network = client.detect_network(phone)
        print(f"  {phone} → {network}")
    
    # Test reference formatting
    print("\n🔗 Testing reference formatting:")
    test_refs = [
        "REF WITH SPACES",
        "very-long-reference-that-exceeds-thirty-characters",
        "normal_ref_123"
    ]
    
    for ref in test_refs:
        formatted = ref.replace(" ", "")[:30]
        print(f"  '{ref}' → '{formatted}' (length: {len(formatted)})")
    
    # Test status normalization
    print("\n📊 Testing status normalization:")
    test_statuses = [
        {"status": "Success"},
        {"status": "Failed"}, 
        {"status": "Pending"},
        {"status": "Cancelled"},
        {"status": "unknown"}
    ]
    
    for status_data in test_statuses:
        normalized = client.get_transaction_status(status_data)
        print(f"  {status_data['status']} → {normalized}")
    
    print("\n✅ All LivePay client tests passed!")
    return True

def test_livepay_provider():
    """Test LivePay provider configuration."""
    print("\n🔧 Testing LivePay Provider Configuration...")
    
    provider = PaymentProvider.objects.filter(
        provider_type="LIVE", 
        is_active=True
    ).first()
    
    if provider:
        print(f"✅ Found active LivePay provider: {provider.name}")
        print(f"   Environment: {provider.environment}")
        print(f"   API Key: {provider.api_key[:10]}..." if provider.api_key else "   API Key: Not set")
        print(f"   Account Number: {provider.api_secret[:10]}..." if provider.api_secret else "   Account Number: Not set")
        
        if provider.api_key and provider.api_secret:
            print("✅ Provider credentials are configured")
        else:
            print("⚠️  Provider credentials are missing")
    else:
        print("⚠️  No active LivePay provider found")
        print("   Create one in Django admin: /admin/")
    
    return True

def test_webhook_signature():
    """Test webhook signature verification."""
    print("\n🔐 Testing Webhook Signature Verification...")
    
    # Test data matching the webhook documentation
    test_payload = {
        "status": "Success",
        "customer_reference": "INV123456789",
        "internal_reference": "550e8400-e29b-41d4-a716-446655440000"
    }
    
    webhook_url = "https://spotpay.it.com/payments/webhook/live/ipn/"
    secret_key = "test_secret_key"
    timestamp = "1705314900"
    
    # Generate expected signature
    import hmac
    import hashlib
    
    string_to_sign = (
        webhook_url + 
        timestamp + 
        test_payload["status"] + 
        test_payload["customer_reference"] + 
        test_payload["internal_reference"]
    )
    
    expected_signature = hmac.new(
        secret_key.encode(),
        string_to_sign.encode(),
        hashlib.sha256
    ).hexdigest()
    
    signature_header = f"t={timestamp},v={expected_signature}"
    
    print(f"   String to sign: {string_to_sign}")
    print(f"   Expected signature: {expected_signature}")
    print(f"   Signature header: {signature_header}")
    
    # Test verification
    is_valid = LivePayClient.verify_webhook_signature(
        secret_key=secret_key,
        signature_header=signature_header,
        payload=test_payload,
        webhook_url=webhook_url
    )
    
    if is_valid:
        print("✅ Webhook signature verification works correctly")
    else:
        print("❌ Webhook signature verification failed")
    
    return is_valid

def main():
    """Run all tests."""
    print("🚀 LivePay Integration Test Suite")
    print("=" * 50)
    
    tests = [
        test_livepay_client,
        test_livepay_provider, 
        test_webhook_signature
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! LivePay integration is ready.")
    else:
        print("⚠️  Some tests failed. Check the output above.")
    
    print("\n📝 Next Steps:")
    print("1. Configure LivePay provider in Django admin")
    print("2. Set your actual API key and account number")
    print("3. Test with real transactions in sandbox mode")
    print("4. Configure webhook URL in LivePay dashboard")

if __name__ == "__main__":
    main()
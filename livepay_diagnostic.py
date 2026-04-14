from payments.models import PaymentProvider
from payments.live_client import LivePayClient
import json
import traceback

print("=== LIVEPAY DIAGNOSTIC ===")

# 1. Check provider configuration
provider = PaymentProvider.objects.filter(provider_type='LIVE', is_active=True).first()
if not provider:
    print("✗ No active LivePay provider found")
    exit()

print(f"✓ Found active LivePay provider: {provider.name}")
print(f"  Account Number: {provider.api_key}")
print(f"  Bearer Token: {provider.api_secret[:20]}...")
print(f"  Environment: {provider.environment}")
print(f"  Webhook Secret: {getattr(provider, 'webhook_secret', 'Not set')}")

# 2. Test API connection
print("\n=== TESTING API CONNECTION ===")
try:
    client = LivePayClient(
        account_number=provider.api_key,
        bearer_token=provider.api_secret,
        environment=provider.environment.lower()
    )
    
    # Test with a small amount
    test_phone = "256700000001"
    test_amount = 100
    test_ref = f"DIAG_{int(__import__('time').time())}"
    
    print(f"Testing collect_money with:")
    print(f"  Phone: {test_phone}")
    print(f"  Amount: {test_amount}")
    print(f"  Reference: {test_ref}")
    
    result = client.collect_money(
        phone_number=test_phone,
        amount=test_amount,
        reference=test_ref,
        reason="Diagnostic test"
    )
    
    print(f"\nAPI Response:")
    print(json.dumps(result, indent=2))
    
    if result.get('success'):
        print("✓ API call successful - prompt should be sent")
    else:
        print(f"✗ API call failed: {result.get('message', 'Unknown error')}")
        
except Exception as e:
    print(f"✗ Exception occurred: {str(e)}")
    print("Full traceback:")
    traceback.print_exc()

# 3. Check recent payment attempts
print("\n=== RECENT PAYMENT ATTEMPTS ===")
try:
    from payments.models import Payment
    recent_payments = Payment.objects.filter(provider_type='LIVE').order_by('-created_at')[:5]
    
    if recent_payments:
        for payment in recent_payments:
            print(f"Payment {payment.id}: {payment.status} - {payment.amount} - {payment.created_at}")
    else:
        print("No recent LivePay payments found")
except Exception as e:
    print(f"Error checking payments: {e}")

print("\n=== DIAGNOSTIC COMPLETE ===")
from payments.live_client import LivePayClient
from payments.models import PaymentProvider

# Get the LivePay provider
provider = PaymentProvider.objects.filter(provider_type='LIVE', is_active=True).first()

if provider:
    print(f"Testing LivePay credentials:")
    print(f"Account Number: {provider.api_key}")
    print(f"Bearer Token: {provider.api_secret[:20]}...")
    
    # Initialize client
    client = LivePayClient(
        account_number=provider.api_key,
        bearer_token=provider.api_secret,
        environment=provider.environment.lower()
    )
    
    # Test with collect_money (this will show if credentials work)
    try:
        result = client.collect_money(
            phone_number="256700000000",  # Test number
            amount=1000,
            reference="TEST_" + str(int(__import__('time').time())),
            reason="Test payment"
        )
        print(f"✓ API Response: {result}")
        if result.get('success'):
            print("✓ LivePay credentials are VALID")
        else:
            print(f"✗ LivePay error: {result.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"✗ LivePay API error: {str(e)}")
else:
    print("No LivePay provider found")
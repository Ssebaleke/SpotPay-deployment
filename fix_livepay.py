from payments.models import PaymentProvider

# Delete any existing LivePay providers
PaymentProvider.objects.filter(provider_type='LIVE').delete()

# Create new active LivePay provider
provider = PaymentProvider.objects.create(
    name="LivePay",
    provider_type="LIVE", 
    api_key="YOUR_LIVEPAY_ACCOUNT_NUMBER",
    api_secret="YOUR_LIVEPAY_BEARER_TOKEN",
    webhook_secret="YOUR_LIVEPAY_WEBHOOK_SECRET",
    environment="production",
    is_active=True
)

print(f"Created active LivePay provider ID: {provider.id}")
print("Update credentials in Django admin with real LivePay values")
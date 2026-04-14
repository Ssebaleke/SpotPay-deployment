#!/usr/bin/env python3

# Check all LivePay providers in database
from payments.models import PaymentProvider

print("=== ALL LIVEPAY PROVIDERS ===")
live_providers = PaymentProvider.objects.filter(provider_type='LIVE')
if live_providers.exists():
    for i, provider in enumerate(live_providers, 1):
        print(f"\nProvider {i}:")
        print(f"  ID: {provider.id}")
        print(f"  Name: {provider.name}")
        print(f"  Active: {provider.is_active}")
        print(f"  Account Number: {provider.api_key}")
        print(f"  Bearer Token: {provider.api_secret}")
        print(f"  Environment: {provider.environment}")
        print(f"  Webhook Secret: {getattr(provider, 'webhook_secret', 'Not set')}")
else:
    print("No LivePay providers found in database")

print("\n=== ALL PROVIDERS BY TYPE ===")
all_providers = PaymentProvider.objects.all()
for provider in all_providers:
    status = "ACTIVE" if provider.is_active else "INACTIVE"
    print(f"{provider.provider_type}: {provider.name} ({status})")
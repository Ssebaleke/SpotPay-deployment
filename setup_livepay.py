#!/usr/bin/env python3

from payments.models import PaymentProvider

print("=== CHECKING LIVEPAY PROVIDERS ===")
live_providers = PaymentProvider.objects.filter(provider_type='LIVE')

if live_providers.exists():
    print(f"Found {live_providers.count()} LivePay provider(s):")
    for provider in live_providers:
        print(f"  ID: {provider.id}, Name: {provider.name}, Active: {provider.is_active}")
        
    # Activate the first one if inactive
    inactive_provider = live_providers.filter(is_active=False).first()
    if inactive_provider:
        inactive_provider.is_active = True
        inactive_provider.save()
        print(f"✓ Activated LivePay provider: {inactive_provider.name}")
    else:
        print("All LivePay providers are already active")
else:
    print("No LivePay providers found. Creating one...")
    
    # Create new LivePay provider with placeholder credentials
    provider = PaymentProvider.objects.create(
        name="LivePay",
        provider_type="LIVE",
        api_key="PLACEHOLDER_ACCOUNT_NUMBER",
        api_secret="PLACEHOLDER_BEARER_TOKEN", 
        webhook_secret="PLACEHOLDER_WEBHOOK_SECRET",
        environment="production",
        is_active=True
    )
    print(f"✓ Created new LivePay provider with ID: {provider.id}")
    print("⚠️  Update credentials in Django admin with real LivePay values")

print("\n=== FINAL STATUS ===")
active_live = PaymentProvider.objects.filter(provider_type='LIVE', is_active=True).first()
if active_live:
    print(f"✓ Active LivePay provider: {active_live.name} (ID: {active_live.id})")
else:
    print("✗ No active LivePay provider")
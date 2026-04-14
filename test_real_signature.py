#!/usr/bin/env python3
"""
Test LivePay signature with real webhook data from logs
"""

import hashlib
import hmac
import json

# Real data from the logs
webhook_secret = "39eacb226cb2466f8b8b8b8b8b8b8b8b"  # Replace with actual
timestamp = "1776144185"
received_signature = "128ca92f5fb6193484ba3ad558c8128eb32c2796a0112c591bbbfb19ad8619e9"

payload = {
    "status": "Success",
    "message": "Payment completed successfully", 
    "customer_reference": "98aef3e796d64e018e9da844a97c09",
    "internal_reference": "db9cd6f6-d175-4b1a-860c-2200b5db82e5",
    "msisdn": "+256776362540",
    "amount": 500,
    "currency": "UGX",
    "provider": "MTN",
    "charge": 15,
    "completed_at": "2026-04-14T05:23:05.000Z"
}

webhook_url = "https://spotpay.it.com/payments/webhook/live/ipn/"

print("Testing LivePay signature formats...")
print(f"Timestamp: {timestamp}")
print(f"Expected signature: {received_signature}")
print()

# Test different formats
formats = [
    # Format 1: timestamp + status + customer_reference + internal_reference
    timestamp + payload["status"] + payload["customer_reference"] + payload["internal_reference"],
    
    # Format 2: Raw JSON body (compact)
    json.dumps(payload, separators=(',', ':')),
    
    # Format 3: Raw JSON body (compact, sorted)
    json.dumps(payload, separators=(',', ':'), sort_keys=True),
    
    # Format 4: timestamp + raw JSON
    timestamp + json.dumps(payload, separators=(',', ':')),
    
    # Format 5: webhook_url + timestamp + status + customer_ref + internal_ref
    webhook_url + timestamp + payload["status"] + payload["customer_reference"] + payload["internal_reference"],
    
    # Format 6: Just the raw JSON body as received
    '{"status":"Success","message":"Payment completed successfully","customer_reference":"98aef3e796d64e018e9da844a97c09","internal_reference":"db9cd6f6-d175-4b1a-860c-2200b5db82e5","msisdn":"+256776362540","amount":500,"currency":"UGX","provider":"MTN","charge":15,"completed_at":"2026-04-14T05:23:05.000Z"}',
    
    # Format 7: timestamp + raw body
    timestamp + '{"status":"Success","message":"Payment completed successfully","customer_reference":"98aef3e796d64e018e9da844a97c09","internal_reference":"db9cd6f6-d175-4b1a-860c-2200b5db82e5","msisdn":"+256776362540","amount":500,"currency":"UGX","provider":"MTN","charge":15,"completed_at":"2026-04-14T05:23:05.000Z"}',
]

for i, signed_data in enumerate(formats, 1):
    signature = hmac.new(
        webhook_secret.encode(),
        signed_data.encode(),
        hashlib.sha256
    ).hexdigest()
    
    match = hmac.compare_digest(signature, received_signature)
    
    print(f"Format {i}: {'✅ MATCH' if match else '❌ No match'}")
    print(f"  Signed data: {repr(signed_data[:100])}...")
    print(f"  Generated: {signature}")
    print()
    
    if match:
        print(f"🎉 FOUND CORRECT FORMAT {i}!")
        break

print("If no match found, LivePay might be using a different secret key or format.")
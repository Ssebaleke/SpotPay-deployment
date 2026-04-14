#!/usr/bin/env python3
"""
Debug LivePay webhook signature verification.
This script tests different signature formats to find the correct one.
"""

import hashlib
import hmac
import time
import json

def test_signature_formats(secret_key, signature_header, payload, webhook_url=""):
    """Test different signature formats to find the correct one."""
    
    print(f"=== SIGNATURE DEBUG ===")
    print(f"Secret Key: {secret_key}")
    print(f"Signature Header: {signature_header}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print(f"Webhook URL: {webhook_url}")
    print()
    
    # Parse signature header
    try:
        parts = {}
        for part in signature_header.split(","):
            k, v = part.split("=", 1)
            parts[k.strip()] = v.strip()
        
        timestamp = parts.get("t", "")
        received_sig = parts.get("v", "")
        
        print(f"Parsed timestamp: {timestamp}")
        print(f"Parsed signature: {received_sig}")
        print()
        
        if not timestamp or not received_sig:
            print("ERROR: Missing timestamp or signature")
            return False
            
    except Exception as e:
        print(f"ERROR parsing signature header: {e}")
        return False
    
    # Test different signed data formats
    formats_to_test = [
        # Format 1: Original format
        {
            "name": "Original format",
            "data": webhook_url + timestamp + str(payload.get("status", "")) + str(payload.get("customer_reference", "")) + str(payload.get("internal_reference", ""))
        },
        # Format 2: Without webhook_url
        {
            "name": "Without webhook_url",
            "data": timestamp + str(payload.get("status", "")) + str(payload.get("customer_reference", "")) + str(payload.get("internal_reference", ""))
        },
        # Format 3: JSON payload + timestamp
        {
            "name": "JSON payload + timestamp",
            "data": json.dumps(payload, separators=(',', ':'), sort_keys=True) + timestamp
        },
        # Format 4: Timestamp + JSON payload
        {
            "name": "Timestamp + JSON payload",
            "data": timestamp + json.dumps(payload, separators=(',', ':'), sort_keys=True)
        },
        # Format 5: Just JSON payload
        {
            "name": "Just JSON payload",
            "data": json.dumps(payload, separators=(',', ':'), sort_keys=True)
        },
        # Format 6: Raw body (if we had it)
        {
            "name": "Timestamp + status + customer_ref + internal_ref",
            "data": timestamp + payload.get("status", "") + payload.get("customer_reference", "") + payload.get("internal_reference", "")
        },
        # Format 7: Different order
        {
            "name": "customer_ref + internal_ref + status + timestamp",
            "data": payload.get("customer_reference", "") + payload.get("internal_reference", "") + payload.get("status", "") + timestamp
        },
        # Format 8: All fields concatenated
        {
            "name": "All fields concatenated",
            "data": "".join([str(v) for v in payload.values()]) + timestamp
        }
    ]
    
    for fmt in formats_to_test:
        try:
            signed_data = fmt["data"]
            expected = hmac.new(
                secret_key.encode(),
                signed_data.encode(),
                hashlib.sha256
            ).hexdigest()
            
            matches = hmac.compare_digest(expected, received_sig)
            
            print(f"Format: {fmt['name']}")
            print(f"Signed data: {repr(signed_data)}")
            print(f"Expected sig: {expected}")
            print(f"Received sig: {received_sig}")
            print(f"MATCH: {matches}")
            print("-" * 50)
            
            if matches:
                print(f"✅ FOUND CORRECT FORMAT: {fmt['name']}")
                return True
                
        except Exception as e:
            print(f"Error testing format '{fmt['name']}': {e}")
            print("-" * 50)
    
    print("❌ No matching signature format found")
    return False

if __name__ == "__main__":
    # Test with sample data - replace with actual webhook data
    secret_key = "39eacb226cb2466f8b8b8b8b8b8b8b8b"  # Replace with actual webhook secret
    
    # Sample signature header - replace with actual
    signature_header = "t=1703123456,v=abc123def456"
    
    # Sample payload - replace with actual webhook payload
    payload = {
        "status": "Success",
        "customer_reference": "12345678901234567890123456789012",
        "internal_reference": "LP-UUID-HERE",
        "amount": 1000,
        "currency": "UGX"
    }
    
    webhook_url = "https://spotpay.it.com/payments/webhook/live/ipn/"
    
    test_signature_formats(secret_key, signature_header, payload, webhook_url)
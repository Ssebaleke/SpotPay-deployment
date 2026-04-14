from payments.live_client import LivePayClient
from payments.models import PaymentProvider
import hashlib
import hmac

# Get webhook secret
provider = PaymentProvider.objects.filter(provider_type='LIVE', is_active=True).first()
webhook_secret = provider.webhook_secret

# Test data from logs
payload = {
    "status": "Success",
    "message": "Payment completed successfully", 
    "customer_reference": "7c46654f802c434bab653194fe9540",
    "internal_reference": "cebc106c-39ef-456f-a6e0-c048de4f7067",
    "msisdn": "+256776362540",
    "amount": 1000,
    "currency": "UGX",
    "provider": "MTN",
    "charge": 30,
    "completed_at": "2026-04-14T04:56:03.000Z"
}

signature_header = "t=1776142563,v=443392f45c0ca8fbccddc41f8595d41bc91ee9b65fbcf223ab4364e9dd957c4c"
webhook_url = "https://spotpay.it.com/payments/webhook/live/ipn/"

print("=== LIVEPAY SIGNATURE DEBUG ===")
print(f"Webhook Secret: {webhook_secret}")
print(f"Signature Header: {signature_header}")
print(f"Webhook URL: {webhook_url}")

# Parse signature
parts = {}
for part in signature_header.split(","):
    k, v = part.split("=", 1)
    parts[k.strip()] = v.strip()

timestamp = parts.get("t", "")
received_sig = parts.get("v", "")

print(f"Timestamp: {timestamp}")
print(f"Received Signature: {received_sig}")

# Build signed data string
signed_data = (
    webhook_url
    + timestamp
    + str(payload.get("status", ""))
    + str(payload.get("customer_reference", ""))
    + str(payload.get("internal_reference", ""))
)

print(f"Signed Data String: '{signed_data}'")

# Calculate expected signature
expected = hmac.new(
    webhook_secret.encode(),
    signed_data.encode(),
    hashlib.sha256
).hexdigest()

print(f"Expected Signature: {expected}")
print(f"Signatures Match: {hmac.compare_digest(expected, received_sig)}")

# Test with LivePayClient method
valid = LivePayClient.verify_webhook_signature(
    secret_key=webhook_secret,
    signature_header=signature_header,
    payload=payload,
    webhook_url=webhook_url
)

print(f"LivePayClient Verification: {valid}")
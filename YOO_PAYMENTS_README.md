# Yo! Payments Integration — SpotPay

Production-ready Django integration for the **Yo! Payments Business API** (Uganda).

---

## Files

```
payments/
├── yoo_client.py          # YoPaymentsClient — all API methods
├── exceptions.py          # YoPaymentsError, YoNetworkError, YoValidationError
├── adapters/yoo.py        # SpotPay adapter (bridges payment engine → client)
├── ipn_views.py           # IPN handlers (success + failure notifications)
├── views.py               # MakyPay webhook + generic payment views
├── urls.py                # URL routing
└── tests/
    └── test_yo_client.py  # Unit + mock integration tests
```

---

## Setup

### 1. Add credentials to PaymentProvider (Django Admin)

Go to **Admin → Payment Providers → Add**:

| Field         | Value                        |
|---------------|------------------------------|
| Name          | Yo! Uganda                   |
| Provider type | YOO                          |
| API Key       | `your-yo-api-username`       |
| API Secret    | `your-yo-api-password`       |
| Is active     | ✅                            |

Credentials are passed directly to `YoPaymentsClient(username=..., password=...)`.  
They are **never** stored in environment variables at runtime.

### 2. Optional env overrides

```env
YO_API_PRIMARY_URL=https://paymentsapi1.yo.co.ug/ybs/task.php
YO_API_BACKUP_URL=https://paymentsapi2.yo.co.ug/ybs/task.php
```

### 3. IPN URLs to configure in your Yo! account

```
InstantNotificationUrl : https://spotpay.it.com/payments/webhook/yoo/ipn/
FailureNotificationUrl : https://spotpay.it.com/payments/webhook/yoo/failure/
```

These are also passed per-request in `deposit_funds()` automatically.

---

## Payment Flow

```
Customer clicks Buy on captive portal
        ↓
POST /api/portal/<uuid>/buy-api/
        ↓
initiate_payment() → Payment(status=PENDING) created
        ↓
YooAdapter.charge() → YoPaymentsClient.deposit_funds()
        ↓
Yo! sends USSD prompt to customer's phone
        ↓
Customer approves on phone
        ↓
Yo! POSTs XML to InstantNotificationUrl
        ↓
yoo_ipn() → payment.mark_success() → issue_voucher() → SMS sent
        ↓
portal.js polls /payments/status/<uuid>/ → gets voucher code
        ↓
Auto-login on MikroTik hotspot
```

If customer declines or times out:
```
Yo! POSTs XML to FailureNotificationUrl
        ↓
yoo_failure_notification() → payment.mark_failed()
        ↓
portal.js polls → gets FAILED → shows error message
```

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/payments/webhook/yoo/ipn/` | Yo! success IPN |
| POST | `/payments/webhook/yoo/failure/` | Yo! failure IPN |
| GET  | `/payments/status/<reference>/` | Poll payment status |

---

## curl Examples

### Initiate a payment (from portal)
```bash
curl -X POST https://spotpay.it.com/api/portal/<location-uuid>/buy-api/ \
  -H "Content-Type: application/json" \
  -d '{
    "package_id": 1,
    "phone": "256771234567",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "ip_address": "192.168.88.100"
  }'
```

Response:
```json
{
  "success": true,
  "payment_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "reference": "YO-TXN-REF-001",
  "status": "PENDING",
  "status_url": "https://spotpay.it.com/payments/status/550e8400-e29b-41d4-a716-446655440000/",
  "message": "Please approve the payment on your phone."
}
```

### Poll payment status
```bash
curl https://spotpay.it.com/payments/status/550e8400-e29b-41d4-a716-446655440000/
```

Response (pending):
```json
{"success": true, "status": "PENDING", "message": "Please approve the payment on your phone."}
```

Response (success):
```json
{"success": true, "status": "SUCCESS", "voucher": "ABC123XYZ", "message": "Payment successful."}
```

### Simulate Yo! IPN (for testing)
```bash
curl -X POST https://spotpay.it.com/payments/webhook/yoo/ipn/ \
  -H "Content-Type: text/xml" \
  -d '<?xml version="1.0" encoding="UTF-8"?>
<AutoCreate>
  <Response>
    <Status>OK</Status>
    <StatusCode>0</StatusCode>
    <TransactionStatus>SUCCEEDED</TransactionStatus>
    <TransactionReference>YO-TXN-REF-001</TransactionReference>
    <InternalReference>550e8400-e29b-41d4-a716-446655440000</InternalReference>
  </Response>
</AutoCreate>'
```

---

## Service Layer Example

```python
from payments.yoo_client import YoPaymentsClient
from payments.exceptions import YoPaymentsError

client = YoPaymentsClient(username="user", password="pass")

# 1. Initiate deposit
result = client.deposit_funds(
    amount=5000,
    account="256771234567",
    reference="ORDER-abc123",
    narrative="Internet voucher",
    notification_url="https://spotpay.it.com/payments/webhook/yoo/ipn/",
    failure_url="https://spotpay.it.com/payments/webhook/yoo/failure/",
)

if YoPaymentsClient.is_pending(result):
    print("USSD prompt sent — waiting for IPN")
elif YoPaymentsClient.is_error(result):
    raise YoPaymentsError(result["error_message"])

# 2. Poll status (if IPN not received after timeout)
status = client.check_transaction_status("ORDER-abc123")
if YoPaymentsClient.is_success(status):
    print("Confirmed:", status["transaction_reference"])

# 3. Verify account before charging
validity = client.verify_account_validity("256771234567", provider_code="MTN")
if YoPaymentsClient.is_success(validity):
    print("Account is valid")

# 4. Check balance
balance = client.check_balance()
print("Balance:", balance["balance"])
```

---

## Running Tests

```bash
python manage.py test payments.tests.test_yo_client
```

Tests cover:
- XML request building and escaping
- XML response parsing (success / pending / error)
- Response classification helpers
- Phone normalization and validation
- Endpoint fallback on timeout (mock-based)
- All-endpoints-fail raises `YoNetworkError`
- Correct HTTP headers sent (`Content-Type: text/xml`, `Content-transfer-encoding: text`)

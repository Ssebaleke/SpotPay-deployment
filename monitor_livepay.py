from payments.models import Payment
from django.utils import timezone
from datetime import timedelta

def check_livepay_health():
    """Check LivePay payment success rate in last hour"""
    one_hour_ago = timezone.now() - timedelta(hours=1)
    
    recent_payments = Payment.objects.filter(
        provider_type='LIVE',
        created_at__gte=one_hour_ago
    )
    
    total = recent_payments.count()
    failed = recent_payments.filter(status='FAILED').count()
    
    if total > 0:
        success_rate = ((total - failed) / total) * 100
        print(f"LivePay Success Rate (last hour): {success_rate:.1f}% ({total-failed}/{total})")
        
        if success_rate < 80:
            print("⚠️  LOW SUCCESS RATE - Check for rate limiting")
    else:
        print("No LivePay payments in last hour")

if __name__ == "__main__":
    check_livepay_health()
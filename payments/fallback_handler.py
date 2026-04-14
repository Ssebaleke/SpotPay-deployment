from payments.models import PaymentProvider
from payments.utils import get_payment_adapter
import logging

logger = logging.getLogger(__name__)

def process_payment_with_fallback(payment, data):
    """
    Try LivePay first, fallback to KwaPay if rate limited
    """
    # Try LivePay first
    try:
        live_provider = PaymentProvider.objects.filter(
            provider_type='LIVE', is_active=True
        ).first()
        
        if live_provider:
            adapter = get_payment_adapter(live_provider)
            return adapter.charge(payment, data)
            
    except ValueError as e:
        error_msg = str(e).lower()
        if "too many requests" in error_msg or "rate limit" in error_msg:
            logger.warning("LivePay rate limited, falling back to KwaPay")
            
            # Fallback to KwaPay
            kwa_provider = PaymentProvider.objects.filter(
                provider_type='KWA', is_active=True
            ).first()
            
            if kwa_provider:
                adapter = get_payment_adapter(kwa_provider)
                payment.provider_type = 'KWA'  # Update payment record
                payment.save()
                return adapter.charge(payment, data)
        
        # Re-raise if not rate limiting or no fallback
        raise
    
    raise ValueError("No payment providers available")
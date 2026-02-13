from .models import PaymentProvider
from .services.dummy import DummyProvider


def get_active_provider():
    return PaymentProvider.objects.filter(is_active=True).first()


def load_provider_adapter(provider):
    # Later map provider.name → real adapters
    return DummyProvider()

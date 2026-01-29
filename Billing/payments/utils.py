# payments/utils.py

from payments.models import PaymentProvider


def get_active_provider():
    """
    Return the currently active payment provider.
    Only ONE provider should be active at a time.
    """
    return PaymentProvider.objects.filter(is_active=True).first()


def load_provider_adapter(provider):
    """
    Dynamically load the adapter for the given provider.
    """
    provider_type = provider.provider_type

    if provider_type == "MOMO":
        from payments.adapters.momo import MomoAdapter
        return MomoAdapter(provider)

    if provider_type == "CARD":
        from payments.adapters.card import CardAdapter
        return CardAdapter(provider)

    raise ValueError(f"Unsupported payment provider: {provider_type}")

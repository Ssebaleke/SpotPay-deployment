from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Vendor
from django.conf import settings
from django.core.mail import send_mail
from .models import VendorWallet, WalletPasswordToken


@receiver(post_save, sender=Vendor)
def handle_vendor_wallet_creation(sender, instance, **kwargs):
    """Auto-create wallet when vendor becomes ACTIVE. Send wallet setup email only once."""
    if not instance.is_approved():
        return

    wallet, created = VendorWallet.objects.get_or_create(vendor=instance)

    if created or not wallet.wallet_password:
        WalletPasswordToken.objects.filter(wallet=wallet).delete()
        token = WalletPasswordToken.objects.create(wallet=wallet)

        link = f"{settings.SITE_URL}/wallets/setup-password/{token.token}/"

        send_mail(
            subject="Set your SpotPay Wallet Password",
            message=(
                f"Hello {instance.company_name},\n\n"
                "Your SpotPay wallet is ready.\n\n"
                f"Set your wallet password here:\n{link}\n\n"
                "This link expires in 1 hour.\n\nSpotPay"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.user.email],
            fail_silently=True,
        )

from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Vendor
from django.conf import settings
from sms.services.email_gateway import send_email
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
        to_email = instance.business_email or instance.user.email

        send_email(
            to_email=to_email,
            subject="Set your SpotPay Wallet Password",
            html=(
                f"<p>Hello {instance.company_name},</p>"
                f"<p>Your SpotPay wallet is ready.</p>"
                f"<p><a href='{link}'>Set your wallet password here</a></p>"
                f"<p>This link expires in 1 hour.</p>"
                f"<p>SpotPay Team</p>"
            ),
            text=(
                f"Hello {instance.company_name},\n\n"
                f"Set your wallet password here:\n{link}\n\n"
                "This link expires in 1 hour.\n\nSpotPay"
            ),
        )

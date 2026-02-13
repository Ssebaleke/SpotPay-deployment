from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Vendor
from django.conf import settings
from django.core.mail import send_mail
from .models import VendorWallet, WalletPasswordToken

@receiver(post_save, sender=Vendor)
def handle_vendor_approval(sender, instance, **kwargs):
    if instance.is_approved:
        wallet, created = VendorWallet.objects.get_or_create(vendor=instance)

        if created or not wallet.wallet_password:
            token, _ = WalletPasswordToken.objects.get_or_create(wallet=wallet)

            link = f"{settings.SITE_URL}/wallet/setup-password/{token.token}/"

            send_mail(
                subject="Set your SpotPay Wallet Password",
                message=f"""
Hello {instance.company_name},

Your SpotPay wallet is ready.

Set your wallet password using the link below:
{link}

This link expires in 1 hour.
""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.user.email],
            )

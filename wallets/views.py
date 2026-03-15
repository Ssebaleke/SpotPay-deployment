import random
import uuid
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum

from .models import (
    VendorWallet,
    WalletTransaction,
    WalletPasswordToken,
    WalletOTP,
    WithdrawalRequest,
)

from .decorators import wallet_required


# =====================================================
# HELPERS
# =====================================================

def generate_otp():
    return str(random.randint(100000, 999999))


def wallet_session_valid(request):
    """
    Optional extra safety:
    expire wallet unlock after 10 minutes
    """
    auth_time = request.session.get('wallet_auth_time')
    if not auth_time:
        return False

    return (timezone.now().timestamp() - auth_time) < (10 * 60)


# =====================================================
# WALLET DASHBOARD
# =====================================================

@login_required
@wallet_required
def wallet_dashboard(request):
    vendor = request.user.vendor
    wallet, _ = VendorWallet.objects.get_or_create(vendor=vendor)

    transactions = wallet.transactions.order_by('-created_at')[:10]
    withdrawals = wallet.withdrawals.order_by('-created_at')[:5]

    total_credited = (
        wallet.transactions.filter(transaction_type=WalletTransaction.CREDIT)
        .aggregate(total=Sum('amount'))['total']
        or Decimal('0.00')
    )
    total_withdrawn = (
        wallet.transactions.filter(
            transaction_type=WalletTransaction.DEBIT,
            reason='WITHDRAWAL'
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0.00')
    )
    pending_withdrawals_total = (
        wallet.withdrawals.filter(status=WithdrawalRequest.STATUS_PENDING)
        .aggregate(total=Sum('amount'))['total']
        or Decimal('0.00')
    )

    return render(request, 'wallets/dashboard.html', {
        'wallet': wallet,
        'transactions': transactions,
        'withdrawals': withdrawals,
        'total_credited': total_credited,
        'total_withdrawn': total_withdrawn,
        'pending_withdrawals_total': pending_withdrawals_total,
    })


@login_required
@wallet_required
def wallet_withdrawal_history(request):
    vendor = request.user.vendor
    wallet, _ = VendorWallet.objects.get_or_create(vendor=vendor)
    withdrawals = wallet.withdrawals.order_by('-created_at')

    return render(request, 'wallets/withdrawal_history.html', {
        'wallet': wallet,
        'withdrawals': withdrawals,
    })


# =====================================================
# WALLET AUTH (PASSWORD UNLOCK)
# =====================================================

@login_required
def wallet_authenticate(request):
    vendor = request.user.vendor
    wallet, _ = VendorWallet.objects.get_or_create(vendor=vendor)

    if not wallet.wallet_password:
        return redirect('wallet_locked')

    if request.method == 'POST':
        password = request.POST.get('password', '').strip()

        if not wallet.check_wallet_password(password):
            messages.error(request, "Invalid wallet password.")
            return render(request, 'wallets/authenticate.html')

        # 🔐 wallet session starts HERE
        request.session['wallet_authenticated'] = True
        request.session['wallet_auth_time'] = timezone.now().timestamp()
        request.session['wallet_otp_verified'] = False

        messages.success(request, "Wallet unlocked.")
        return redirect('wallet_dashboard')

    return render(request, 'wallets/authenticate.html')


# =====================================================
# WALLET LOCKED (NO PASSWORD SET)
# =====================================================

@login_required
def wallet_locked(request):
    return render(request, 'wallets/wallet_locked.html')


# =====================================================
# RESET WALLET PASSWORD (REQUEST)
# =====================================================

@login_required
def wallet_password_reset_request(request):
    vendor = request.user.vendor
    wallet, _ = VendorWallet.objects.get_or_create(vendor=vendor)

    WalletPasswordToken.objects.filter(wallet=wallet).delete()
    token = WalletPasswordToken.objects.create(wallet=wallet)

    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    link = f"{site_url}/wallets/setup-password/{token.token}/"

    send_mail(
        "Reset SpotPay Wallet Password",
        f"Click the link below:\n\n{link}",
        settings.DEFAULT_FROM_EMAIL,
        [request.user.email],
        fail_silently=False,
    )

    messages.success(request, "Wallet reset link sent to your email.")
    return redirect('vendor_dashboard')


# =====================================================
# SET WALLET PASSWORD
# =====================================================

def setup_wallet_password(request, token):
    token_obj = get_object_or_404(
        WalletPasswordToken,
        token=token,
        expires_at__gt=timezone.now()
    )

    if request.method == 'POST':
        password = request.POST.get('password')
        confirm = request.POST.get('confirm')

        if password != confirm:
            return render(request, 'wallets/setup_password.html', {
                'error': 'Passwords do not match'
            })

        token_obj.wallet.set_wallet_password(password)
        token_obj.delete()

        messages.success(request, "Wallet password set successfully.")
        return redirect('wallet_authenticate')

    return render(request, 'wallets/setup_password.html')


# =====================================================
# SEND OTP (FOR WITHDRAWAL)
# =====================================================

@login_required
@wallet_required
def wallet_send_otp(request):
    vendor = request.user.vendor

    WalletOTP.objects.filter(
        vendor=vendor,
        is_used=False
    ).update(is_used=True)

    otp = generate_otp()

    WalletOTP.objects.create(
        vendor=vendor,
        code=otp,
        expires_at=timezone.now() + timedelta(minutes=5)
    )

    send_mail(
        "SpotPay Wallet OTP",
        f"Your OTP is: {otp}",
        settings.DEFAULT_FROM_EMAIL,
        [request.user.email],
        fail_silently=False,
    )

    messages.info(request, "OTP sent to your email.")
    return redirect('wallet_verify_otp')


# =====================================================
# VERIFY OTP
# =====================================================

@login_required
@wallet_required
def wallet_verify_otp(request):
    vendor = request.user.vendor

    if request.method == 'POST':
        code = request.POST.get('otp')

        otp = WalletOTP.objects.filter(
            vendor=vendor,
            code=code,
            is_used=False,
            expires_at__gt=timezone.now()
        ).first()

        if not otp:
            messages.error(request, "Invalid or expired OTP.")
            return render(request, 'wallets/verify_otp.html')

        otp.is_used = True
        otp.save(update_fields=['is_used'])

        request.session['wallet_otp_verified'] = True
        messages.success(request, "OTP verified.")
        return redirect('wallet_withdraw')

    return render(request, 'wallets/verify_otp.html')


# =====================================================
# WITHDRAW (CREATE REQUEST ONLY)
# =====================================================

@login_required
@wallet_required
def wallet_withdraw(request):
    if not request.session.get('wallet_otp_verified'):
        return redirect('wallet_send_otp')

    vendor = request.user.vendor
    wallet = vendor.wallet

    if request.method == 'POST':
        withdrawal_mode = request.POST.get('withdrawal_mode', 'pending')

        try:
            amount = Decimal(request.POST.get('amount'))
        except Exception:
            messages.error(request, "Invalid amount.")
            return redirect('wallet_withdraw')

        if amount <= 0:
            messages.error(request, "Amount must be greater than zero.")
            return redirect('wallet_withdraw')

        if amount > wallet.balance:
            messages.error(request, "Insufficient wallet balance.")
            return redirect('wallet_withdraw')

        if withdrawal_mode == 'instant':
            with transaction.atomic():
                locked_wallet = VendorWallet.objects.select_for_update().get(pk=wallet.pk)

                if amount > locked_wallet.balance:
                    messages.error(request, "Insufficient wallet balance.")
                    return redirect('wallet_withdraw')

                locked_wallet.balance -= amount
                locked_wallet.save(update_fields=['balance', 'updated_at'])

                withdrawal = WithdrawalRequest.objects.create(
                    wallet=locked_wallet,
                    amount=amount,
                    status=WithdrawalRequest.STATUS_PAID,
                    reference=str(uuid.uuid4()),
                )

                WalletTransaction.objects.create(
                    wallet=locked_wallet,
                    amount=amount,
                    transaction_type=WalletTransaction.DEBIT,
                    reason='WITHDRAWAL',
                    reference=f"AUTO-WD-{withdrawal.reference}",
                )

            messages.success(request, "Instant withdrawal processed successfully.")
        else:
            WithdrawalRequest.objects.create(
                wallet=wallet,
                amount=amount,
                reference=str(uuid.uuid4()),
            )

            messages.success(
                request,
                "Withdrawal request submitted. Awaiting approval."
            )
        return redirect('wallet_dashboard')

    return render(request, 'wallets/withdraw.html', {
        'wallet': wallet
    })


# =====================================================
# LOCK WALLET (WITHOUT LOGOUT)
# =====================================================

@login_required
def wallet_lock(request):
    request.session.pop('wallet_authenticated', None)
    request.session.pop('wallet_auth_time', None)
    request.session.pop('wallet_otp_verified', None)

    messages.info(request, "Wallet locked.")
    return redirect('vendor_dashboard')


# =====================================================
# RESET PASSWORD FROM AUTH SCREEN
# =====================================================

@login_required
def wallet_password_reset_from_auth(request):
    if not hasattr(request.user, 'vendor'):
        return HttpResponseForbidden()

    vendor = request.user.vendor
    wallet, _ = VendorWallet.objects.get_or_create(vendor=vendor)

    WalletPasswordToken.objects.filter(wallet=wallet).delete()
    token = WalletPasswordToken.objects.create(wallet=wallet)

    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    reset_link = f"{site_url}/wallets/setup-password/{token.token}/"

    send_mail(
        "Reset your SpotPay Wallet Password",
        f"""
Hello {vendor.company_name},

You requested to reset your SpotPay wallet password.

Click the link below to continue:
{reset_link}

If you did not request this, ignore this email.
""",
        settings.DEFAULT_FROM_EMAIL,
        [request.user.email],
        fail_silently=False,
    )

    messages.success(
        request,
        "A reset link has been sent to your email."
    )

    return redirect('wallet_authenticate')

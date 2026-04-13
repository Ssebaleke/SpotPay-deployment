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
from django.db import transaction
from sms.services.email_gateway import send_email
from django.db.models import Sum

from .models import (
    VendorWallet,
    WalletTransaction,
    WalletPasswordToken,
    WalletOTP,
    WithdrawalRequest,
)

from .decorators import wallet_required
from sms.services.notifications import notify_withdrawal_receipt


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

    send_email(
        to_email=vendor.business_email or request.user.email,
        subject="Reset SpotPay Wallet Password",
        html=f"<p>Hello {vendor.company_name},</p><p>Click the link below to reset your wallet password:</p><p><a href='{link}'>{link}</a></p><p>SpotPay Team</p>",
        text=f"Click the link below to reset your wallet password:\n{link}",
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

    to_email = vendor.business_email or request.user.email
    send_email(
        to_email=to_email,
        subject="SpotPay Wallet OTP",
        html=f"<p>Hello,</p><p>Your verification code is: <strong>{otp}</strong></p><p>Valid for 5 minutes. Do not share with anyone.</p><p>SpotPay Team</p>",
        text=f"Your SpotPay verification code is: {otp}. Valid for 5 minutes.",
    )

    # Also send OTP via SMS if vendor has SMS balance
    if vendor.business_phone:
        try:
            from sms.models import VendorSMSWallet
            from sms.services.sms_gateway import send_sms
            sms_wallet = VendorSMSWallet.objects.filter(vendor=vendor).first()
            if sms_wallet and sms_wallet.balance_units >= 1:
                send_sms(
                    vendor=vendor,
                    phone=vendor.business_phone,
                    message=f"SpotPay Wallet OTP: {otp}. Valid for 5 minutes. Do not share.",
                    purpose="WALLET_OTP",
                )
                sms_wallet.balance_units -= 1
                sms_wallet.save(update_fields=["balance_units"])
        except Exception:
            pass  # SMS failure must never block OTP flow

    messages.info(request, "OTP sent to your email and phone.")
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
        try:
            amount = Decimal(request.POST.get('amount'))
        except Exception:
            messages.error(request, "Invalid amount.")
            return redirect('wallet_withdraw')

        payout_method = request.POST.get('payout_method', 'MTN')
        payout_phone = request.POST.get('payout_phone', '').strip()
        payout_name = request.POST.get('payout_name', '').strip()

        if not payout_phone:
            messages.error(request, "Payout phone/account number is required.")
            return redirect('wallet_withdraw')

        if not payout_name:
            messages.error(request, "Account holder name is required.")
            return redirect('wallet_withdraw')

        if amount <= 0:
            messages.error(request, "Amount must be greater than zero.")
            return redirect('wallet_withdraw')

        if amount < 10000:
            messages.error(request, "Minimum withdrawal amount is UGX 10,000.")
            return redirect('wallet_withdraw')

        # Calculate fees — deducted FROM the amount, vendor receives amount - fees
        from payments.models import PaymentSystemConfig
        config = PaymentSystemConfig.get()
        gateway_fee = config.withdrawal_gateway_fee.quantize(Decimal('1'))
        spotpay_fee = config.withdrawal_spotpay_fee.quantize(Decimal('1'))
        total_fees = gateway_fee + spotpay_fee
        payout_amount = amount - total_fees  # what vendor actually receives

        if payout_amount <= 0:
            messages.error(request, f"Amount too low. Fees are UGX {total_fees:,.0f}.")
            return redirect('wallet_withdraw')

        if amount > wallet.balance:
            messages.error(request, f"Insufficient balance. You have UGX {wallet.balance:,.0f}.")
            return redirect('wallet_withdraw')

        import logging
        import uuid as _uuid
        logger = logging.getLogger(__name__)

        withdrawal_ref = str(_uuid.uuid4())
        disbursement_success = False
        disbursement_error = None

        # ── Step 1: Attempt disbursement via active provider ──
        try:
            from payments.models import PaymentProvider

            # Try KwaPay first, then LivePay — whichever is active
            provider = (
                PaymentProvider.objects.filter(provider_type='KWA', is_active=True).first()
                or PaymentProvider.objects.filter(provider_type='LIVE', is_active=True).first()
            )

            if provider:
                if provider.provider_type == 'KWA':
                    from payments.kwa_client import KwaPayClient
                    client = KwaPayClient(
                        primary_api=provider.api_key,
                        secondary_api=provider.api_secret,
                    )
                    callback_url = f"{settings.SITE_URL}/payments/webhook/kwa/ipn/"
                    result = client.withdraw(
                        amount=int(payout_amount),
                        phone=payout_phone,
                        callback_url=callback_url,
                    )
                    logger.warning(f"KWA WITHDRAWAL RESULT: {result}")
                    if KwaPayClient.is_failed(result):
                        disbursement_error = result.get('message') or 'Disbursement failed'
                    else:
                        disbursement_success = True

                elif provider.provider_type == 'LIVE':
                    from payments.live_client import LivePayClient
                    client = LivePayClient(
                        public_key=provider.api_key,
                        secret_key=provider.api_secret,
                    )
                    result = client.send(
                        amount=int(payout_amount),
                        phone=payout_phone,
                        reference=withdrawal_ref[:30],
                    )
                    logger.warning(f"LIVEPAY SEND RESULT: {result}")
                    if not result.get('success'):
                        disbursement_error = result.get('message') or 'Disbursement failed'
                    else:
                        disbursement_success = True
            else:
                disbursement_error = "No disbursement provider configured"

        except Exception as e:
            logger.warning(f"WITHDRAWAL DISBURSEMENT EXCEPTION: {e}")
            disbursement_error = str(e)

        # ── Step 2: Only deduct wallet and record if disbursement succeeded ──
        # If disbursement failed — do NOT deduct, show error to vendor
        if not disbursement_success:
            messages.error(request, f"Withdrawal failed: {disbursement_error}. Your balance has not been deducted.")
            return redirect('wallet_withdraw')

        withdrawal_status = WithdrawalRequest.STATUS_PAID

        with transaction.atomic():
            locked_wallet = VendorWallet.objects.select_for_update().get(pk=wallet.pk)

            if amount > locked_wallet.balance:
                messages.error(request, "Insufficient wallet balance.")
                return redirect('wallet_withdraw')

            locked_wallet.balance -= amount
            locked_wallet.save(update_fields=['balance', 'updated_at'])

            withdrawal = WithdrawalRequest.objects.create(
                wallet=locked_wallet,
                amount=payout_amount,
                payout_method=payout_method,
                payout_phone=payout_phone,
                payout_name=payout_name,
                status=withdrawal_status,
                reference=withdrawal_ref,
            )

            WalletTransaction.objects.create(
                wallet=locked_wallet,
                amount=amount,
                transaction_type=WalletTransaction.DEBIT,
                reason='WITHDRAWAL',
                reference=f"WD-{withdrawal.reference}",
            )

            # Credit SpotPay earnings from withdrawal fee
            if spotpay_fee > 0:
                from wallets.models import SpotPayEarning
                SpotPayEarning.objects.create(
                    source='WITHDRAWAL_FEE',
                    amount=spotpay_fee,
                    reference=f"WD-FEE-{withdrawal.reference}",
                )

        request.session.pop('wallet_otp_verified', None)

        try:
            notify_withdrawal_receipt(withdrawal)
        except Exception:
            pass
        messages.success(request, "Withdrawal processed successfully. A receipt has been sent to your email.")

        return redirect('wallet_dashboard')

    return render(request, 'wallets/withdraw.html', {
        'wallet': wallet,
        'gateway_fee': config.withdrawal_gateway_fee.quantize(Decimal('1')),
        'spotpay_fee': config.withdrawal_spotpay_fee.quantize(Decimal('1')),
        'total_fees': (config.withdrawal_gateway_fee + config.withdrawal_spotpay_fee).quantize(Decimal('1')),
    })


# =====================================================
# MOBILE MONEY NAME LOOKUP
# =====================================================

@login_required
def lookup_name(request):
    from django.http import JsonResponse
    import requests as http_requests
    from payments.models import PaymentProvider

    phone = request.GET.get('phone', '').strip()
    method = request.GET.get('method', '').upper()

    if not phone:
        return JsonResponse({'success': False, 'error': 'Phone number required'})

    # Try MakyPay name lookup if provider is configured
    provider = PaymentProvider.objects.filter(is_active=True).first()
    if provider and provider.base_url:
        try:
            resp = http_requests.post(
                f"{provider.base_url.rstrip('/')}/name-lookup",
                json={'phone': phone},
                headers={
                    'Authorization': f'Bearer {provider.api_key}',
                    'Content-Type': 'application/json',
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                name = data.get('name') or data.get('account_name') or data.get('full_name')
                if name:
                    return JsonResponse({'success': True, 'name': name})
        except Exception:
            pass

    return JsonResponse({'success': False, 'error': 'Could not verify number. Enter name manually.'})


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

    send_email(
        to_email=vendor.business_email or request.user.email,
        subject="Reset your SpotPay Wallet Password",
        html=f"<p>Hello {vendor.company_name},</p><p>You requested to reset your SpotPay wallet password.</p><p><a href='{reset_link}'>{reset_link}</a></p><p>If you did not request this, ignore this email.</p><p>SpotPay Team</p>",
        text=f"Hello {vendor.company_name},\n\nReset your wallet password:\n{reset_link}\n\nIf you did not request this, ignore this email.",
    )

    messages.success(
        request,
        "A reset link has been sent to your email."
    )

    return redirect('wallet_authenticate')

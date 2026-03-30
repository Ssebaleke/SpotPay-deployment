from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from decimal import Decimal
from datetime import timedelta

from sms.services.email_gateway import send_email

from payments.models import Payment, PaymentProvider
from sms.models import VendorSMSWallet
from wallets.models import VendorWallet, WithdrawalRequest, WalletTransaction
from sms.services.notifications import notify_withdrawal_status, notify_vendor_approval, notify_vendor_registration, notify_admin_new_vendor

from .forms import VendorRegistrationForm, VendorProfileForm
from .models import Vendor
from hotspot.models import HotspotLocation


# =====================================================
# PUBLIC LANDING PAGE
# =====================================================

def learning_page(request):
    return render(request, 'accounts/home.html')


# =====================================================
# VENDOR REGISTRATION
# =====================================================

def vendor_register(request):
    if request.method == 'POST':
        form = VendorRegistrationForm(request.POST)
        if form.is_valid():
            vendor = form.save()
            try:
                notify_vendor_registration(vendor)
                notify_admin_new_vendor(vendor)
            except Exception:
                pass  # never block registration if email fails
            messages.success(
                request,
                'Registration successful! Please wait for admin approval.'
            )
            return redirect('vendor_login')
    else:
        form = VendorRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


# =====================================================
# VENDOR LOGIN
# =====================================================

def vendor_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = request.POST.get('remember_me')

            user = authenticate(username=username, password=password)

            if user is not None and user.is_active:
                if user.is_staff:
                    login(request, user)
                    if not remember_me:
                        request.session.set_expiry(0)
                    else:
                        request.session.set_expiry(1209600)  # 14 days
                    return redirect('admin_dashboard')
                try:
                    vendor = user.vendor
                    if vendor.status == 'ACTIVE':
                        login(request, user)
                        if not remember_me:
                            request.session.set_expiry(0)
                        else:
                            request.session.set_expiry(1209600)  # 14 days
                        return redirect('vendor_dashboard')
                    else:
                        messages.error(
                            request,
                            'Your account is not approved yet or has been suspended.'
                        )
                except Vendor.DoesNotExist:
                    messages.error(request, 'This account is not a vendor.')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_dashboard(request):
    period = request.GET.get('period', '30d')
    now = timezone.now()

    period_start_map = {
        '7d': now - timedelta(days=7),
        '30d': now - timedelta(days=30),
        '90d': now - timedelta(days=90),
        '365d': now - timedelta(days=365),
    }
    start_dt = period_start_map.get(period)

    transactions_scope = Payment.objects.filter(
        purpose="TRANSACTION",
        vendor__isnull=False
    )
    if start_dt:
        transactions_scope = transactions_scope.filter(initiated_at__gte=start_dt)

    total_platform_sales = (
        transactions_scope.filter(status="SUCCESS").aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    total_vendors = Vendor.objects.count()
    active_vendors = Vendor.objects.filter(status="ACTIVE").count()
    pending_vendors = Vendor.objects.filter(status="PENDING").count()

    total_locations = HotspotLocation.objects.count()
    active_locations = HotspotLocation.objects.filter(status="ACTIVE").count()

    total_transactions = transactions_scope.count()
    successful_transactions = transactions_scope.filter(status="SUCCESS").count()
    failed_transactions = transactions_scope.filter(status="FAILED").count()
    pending_transactions = transactions_scope.filter(status="PENDING").count()

    total_wallet_balance = (
        VendorWallet.objects.aggregate(total=Sum("balance"))["total"]
        or Decimal("0.00")
    )
    pending_withdrawals_qs = WithdrawalRequest.objects.filter(status=WithdrawalRequest.STATUS_PENDING)
    pending_withdrawals_count = pending_withdrawals_qs.count()
    pending_withdrawals_total = (
        pending_withdrawals_qs.aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    recent_vendor_activity = transactions_scope.select_related(
        "vendor", "package", "location"
    ).order_by("-initiated_at")[:10]

    vendor_performance = list(
        transactions_scope.values(
            'vendor_id',
            'vendor__company_name'
        ).annotate(
            transaction_count=Count('id'),
            successful_count=Count('id', filter=Q(status='SUCCESS')),
            total_sales=Sum('amount', filter=Q(status='SUCCESS')),
        ).order_by('-total_sales', '-successful_count')[:15]
    )

    for item in vendor_performance:
        success_count = item.get('successful_count') or 0
        transaction_count = item.get('transaction_count') or 0
        item['total_sales'] = item.get('total_sales') or Decimal('0.00')
        item['success_rate'] = (
            round((success_count / transaction_count) * 100, 2)
            if transaction_count > 0 else 0
        )

    # Mon-Sun weekly trend for admin chart
    admin_trend_labels = []
    admin_trend_values = []
    today_date = timezone.localdate()
    days_since_monday = today_date.weekday()
    for day_offset in range(days_since_monday, -1, -1):
        day = today_date - timedelta(days=day_offset)
        day_total = (
            Payment.objects.filter(
                purpose="TRANSACTION",
                status="SUCCESS",
                completed_at__date=day
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        admin_trend_labels.append(day.strftime("%a %d"))
        admin_trend_values.append(float(day_total))

    # vendor success rate for doughnut
    success_rate = round((successful_transactions / total_transactions) * 100) if total_transactions > 0 else 0

    from sms.models import SMSPurchase, SMSProvider
    import requests as http_requests

    # UGSMS live balance
    ugsms_balance_units = "N/A"
    sms_provider = SMSProvider.objects.filter(is_active=True).first()
    if sms_provider:
        try:
            resp = http_requests.get(
                "https://ugsms.com/api/v2/account/balance",
                headers={"X-API-Key": sms_provider.api_key},
                timeout=5
            )
            if resp.status_code == 200:
                rdata = resp.json()
                ugsms_balance_units = rdata.get("balance") or rdata.get("data", {}).get("balance", "N/A")
        except Exception:
            pass

    # Total revenue from vendor SMS purchases
    total_sms_revenue = (
        SMSPurchase.objects.filter(status="SUCCESS").aggregate(total=Sum("amount_paid"))["total"]
        or 0
    )

    pending_vendors_list = Vendor.objects.filter(status='PENDING').select_related('user').order_by('created_at')
    all_vendors_list = Vendor.objects.select_related('user').order_by('-created_at')[:20]
    all_locations_list = HotspotLocation.objects.select_related('vendor').order_by('-created_at')[:20]

    return render(request, 'accounts/admin_dashboard.html', {
        'period': period,
        'total_platform_sales': total_platform_sales,
        'total_vendors': total_vendors,
        'active_vendors': active_vendors,
        'pending_vendors': pending_vendors,
        'total_locations': total_locations,
        'active_locations': active_locations,
        'total_transactions': total_transactions,
        'successful_transactions': successful_transactions,
        'failed_transactions': failed_transactions,
        'pending_transactions': pending_transactions,
        'success_rate': success_rate,
        'total_wallet_balance': total_wallet_balance,
        'pending_withdrawals_count': pending_withdrawals_count,
        'pending_withdrawals_total': pending_withdrawals_total,
        'pending_withdrawals': pending_withdrawals_qs.select_related('wallet', 'wallet__vendor').order_by('-created_at')[:10],
        'recent_vendor_activity': recent_vendor_activity,
        'vendor_performance': vendor_performance,
        'admin_trend_labels': admin_trend_labels,
        'admin_trend_values': admin_trend_values,
        'ugsms_balance_units': ugsms_balance_units,
        'total_sms_revenue': total_sms_revenue,
        'pending_vendors_list': pending_vendors_list,
        'all_vendors_list': all_vendors_list,
        'all_locations_list': all_locations_list,
    })


@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_approve_vendor(request, vendor_id):
    if request.method != 'POST':
        return redirect('admin_dashboard')
    vendor = Vendor.objects.select_related('user').filter(id=vendor_id).first()
    if not vendor:
        messages.error(request, 'Vendor not found.')
        return redirect('admin_dashboard')
    vendor.status = 'ACTIVE'
    vendor.approved_by = request.user
    vendor.approved_at = timezone.now()
    vendor.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
    vendor.user.is_active = True
    vendor.user.save()
    notify_vendor_approval(vendor)
    messages.success(request, f'{vendor.company_name} approved and activated.')
    return redirect('admin_dashboard')


@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_reject_vendor(request, vendor_id):
    if request.method != 'POST':
        return redirect('admin_dashboard')
    vendor = Vendor.objects.select_related('user').filter(id=vendor_id).first()
    if not vendor:
        messages.error(request, 'Vendor not found.')
        return redirect('admin_dashboard')
    vendor.status = 'REJECTED'
    vendor.save(update_fields=['status', 'updated_at'])
    vendor.user.is_active = False
    vendor.user.save()
    messages.success(request, f'{vendor.company_name} rejected.')
    return redirect('admin_dashboard')


@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_suspend_vendor(request, vendor_id):
    if request.method != 'POST':
        return redirect('admin_dashboard')
    vendor = Vendor.objects.select_related('user').filter(id=vendor_id).first()
    if not vendor:
        messages.error(request, 'Vendor not found.')
        return redirect('admin_dashboard')
    vendor.status = 'SUSPENDED'
    vendor.save(update_fields=['status', 'updated_at'])
    vendor.user.is_active = False
    vendor.user.save()
    messages.success(request, f'{vendor.company_name} suspended. They can no longer log in.')
    return redirect('admin_dashboard')


@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_unsuspend_vendor(request, vendor_id):
    if request.method != 'POST':
        return redirect('admin_dashboard')
    vendor = Vendor.objects.select_related('user').filter(id=vendor_id).first()
    if not vendor:
        messages.error(request, 'Vendor not found.')
        return redirect('admin_dashboard')
    vendor.status = 'ACTIVE'
    vendor.save(update_fields=['status', 'updated_at'])
    vendor.user.is_active = True
    vendor.user.save()
    messages.success(request, f'{vendor.company_name} reactivated.')
    return redirect('admin_dashboard')


@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_approve_withdrawal(request, withdrawal_id):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('admin_dashboard')

    with transaction.atomic():
        withdrawal = WithdrawalRequest.objects.select_for_update().select_related('wallet', 'wallet__vendor').filter(
            id=withdrawal_id,
            status=WithdrawalRequest.STATUS_PENDING
        ).first()

        if not withdrawal:
            messages.error(request, 'Withdrawal request not found or already processed.')
            return redirect('admin_dashboard')

        wallet = withdrawal.wallet
        if not wallet:
            messages.error(request, 'Wallet record missing for this withdrawal.')
            return redirect('admin_dashboard')

        if wallet.balance < withdrawal.amount:
            messages.error(request, 'Insufficient wallet balance for approval.')
            return redirect('admin_dashboard')

        wallet.balance = wallet.balance - withdrawal.amount
        wallet.save(update_fields=['balance', 'updated_at'])

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=withdrawal.amount,
            transaction_type=WalletTransaction.DEBIT,
            reason='WITHDRAWAL',
            reference=f"WD-{withdrawal.reference}",
        )

        withdrawal.status = WithdrawalRequest.STATUS_APPROVED
        withdrawal.save(update_fields=['status', 'updated_at'])

    notify_withdrawal_status(withdrawal, "approved")
    messages.success(request, 'Withdrawal approved and wallet debited successfully.')
    return redirect('admin_dashboard')


@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_reject_withdrawal(request, withdrawal_id):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('admin_dashboard')

    withdrawal = WithdrawalRequest.objects.select_related('wallet', 'wallet__vendor').filter(
        id=withdrawal_id,
        status=WithdrawalRequest.STATUS_PENDING
    ).first()

    if not withdrawal:
        messages.error(request, 'Withdrawal request not found or already processed.')
        return redirect('admin_dashboard')

    updated = WithdrawalRequest.objects.filter(
        id=withdrawal_id,
        status=WithdrawalRequest.STATUS_PENDING
    ).update(status=WithdrawalRequest.STATUS_REJECTED)

    if not updated:
        messages.error(request, 'Withdrawal request not found or already processed.')
        return redirect('admin_dashboard')

    notify_withdrawal_status(withdrawal, "rejected")
    messages.success(request, 'Withdrawal request rejected successfully.')
    return redirect('admin_dashboard')


# =====================================================
# VENDOR DASHBOARD (REAL DATA – NO DUMMY)
# =====================================================

@login_required
def vendor_dashboard(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        vendor = request.user.vendor
        if vendor.status != 'ACTIVE' or not request.user.is_active:
            messages.error(request, 'Your account is not approved or has been suspended.')
            return redirect('vendor_login')
    except Vendor.DoesNotExist:
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendor_login')

    # -------------------------------------------------
    # SUBSCRIPTION WARNINGS
    # -------------------------------------------------
    subscription_warnings = []
    locations = vendor.locations.all()

    for location in locations:

        # Never subscribed
        if not location.subscription_active and not location.subscription_expires_at:
            subscription_warnings.append({
                "level": "danger",
                "message": f"{location.site_name}: Subscription required to activate this location"
            })
            continue

        # Has expiry date
        if location.subscription_expires_at:
            days_left = (
                location.subscription_expires_at.date()
                - timezone.now().date()
            ).days

            if days_left < 0:
                subscription_warnings.append({
                    "level": "danger",
                    "message": f"{location.site_name}: Subscription expired"
                })
            elif days_left == 0:
                subscription_warnings.append({
                    "level": "warning",
                    "message": f"{location.site_name}: Subscription expires today"
                })
            elif days_left <= 2:
                subscription_warnings.append({
                    "level": "warning",
                    "message": f"{location.site_name}: Subscription expires in {days_left} days"
                })

    # -------------------------------------------------
    # PAYMENT REFLECTION (REAL DATA)
    # -------------------------------------------------
    vendor_payments = Payment.objects.filter(
        vendor=vendor,
        purpose="TRANSACTION"
    )

    successful_payments_qs = vendor_payments.filter(status="SUCCESS")
    today = timezone.localdate()
    now = timezone.now()
    week_start = today - timedelta(days=today.weekday())  # Monday of current week
    month_start = now.replace(day=1)
    year_start = now.replace(month=1, day=1)

    # Location filter — applies to cards, charts AND transactions table
    location_filter = request.GET.get('location', '').strip()
    if location_filter:
        successful_payments_qs = successful_payments_qs.filter(location_id=location_filter)
        vendor_payments = vendor_payments.filter(location_id=location_filter)

    total_payments_received = (
        successful_payments_qs.aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    todays_payments = successful_payments_qs.filter(
        completed_at__date=today
    )
    todays_payments_total = (
        todays_payments.aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    weekly_payments_total = (
        successful_payments_qs.filter(completed_at__date__gte=week_start).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    monthly_payments_total = (
        successful_payments_qs.filter(completed_at__gte=month_start).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    annual_payments_total = (
        successful_payments_qs.filter(completed_at__gte=year_start).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    trend_labels = []
    trend_values = []
    weekly_buyers_counts = []
    days_since_monday = today.weekday()  # 0=Mon, 6=Sun
    for day_offset in range(days_since_monday, -1, -1):
        day = today - timedelta(days=day_offset)
        day_total = (
            successful_payments_qs.filter(completed_at__date=day).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        day_buyers = successful_payments_qs.filter(completed_at__date=day).count()
        trend_labels.append(day.strftime("%a"))
        trend_values.append(float(day_total))
        weekly_buyers_counts.append(day_buyers)

    successful_payments_count = successful_payments_qs.count()
    pending_payments_count = vendor_payments.filter(status="PENDING").count()
    failed_payments_count = vendor_payments.filter(status="FAILED").count()

    # Calculate progress bar percentages
    total_payments_count = vendor_payments.count()
    if total_payments_count > 0:
        successful_percentage = round((successful_payments_count / total_payments_count) * 100)
        pending_failed_count = pending_payments_count + failed_payments_count
        pending_failed_percentage = round((pending_failed_count / total_payments_count) * 100)
    else:
        successful_percentage = 0
        pending_failed_percentage = 0
    
    # Total payments received percentage (always 100% if there are payments, 0% otherwise)
    total_received_percentage = 100 if total_payments_received > 0 else 0

    # Search + filter
    search_q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    txn_qs = vendor_payments.select_related("package", "location")
    if search_q:
        txn_qs = txn_qs.filter(phone__icontains=search_q)
    if status_filter:
        txn_qs = txn_qs.filter(status=status_filter)
    txn_qs = txn_qs.order_by("-initiated_at")

    from django.core.paginator import Paginator
    paginator = Paginator(txn_qs, 15)
    page_number = request.GET.get('page', 1)
    recent_transactions = paginator.get_page(page_number)

    # -------------------------------------------------
    # SMS WALLET (REAL BALANCE)
    # -------------------------------------------------
    sms_wallet = VendorSMSWallet.objects.filter(vendor=vendor).first()
    sms_balance = sms_wallet.balance_units if sms_wallet else 0

    # Packages for sell-voucher modal
    from packages.models import Package
    vendor_packages = Package.objects.filter(
        location__vendor=vendor, is_active=True
    ).select_related('location').order_by('location__site_name', 'price')

    # -------------------------------------------------
    # DASHBOARD RENDER
    # -------------------------------------------------
    return render(request, 'accounts/dashboard.html', {
        'vendor': vendor,
        'locations_count': locations.filter(is_active=True).count(),
        'subscription_warnings': subscription_warnings,
        'sms_balance': sms_balance,
        'vendor_packages': vendor_packages,
        'total_payments_received': total_payments_received,
        'todays_payments_total': todays_payments_total,
        'weekly_payments_total': weekly_payments_total,
        'monthly_payments_total': monthly_payments_total,
        'annual_payments_total': annual_payments_total,
        'successful_payments_count': successful_payments_count,
        'pending_payments_count': pending_payments_count,
        'failed_payments_count': failed_payments_count,
        'total_received_percentage': total_received_percentage,
        'successful_percentage': successful_percentage,
        'pending_failed_percentage': pending_failed_percentage,
        'recent_transactions': recent_transactions,
        'search_q': search_q,
        'status_filter': status_filter,
        'location_filter': location_filter,
        'vendor_locations': locations,
        'trend_labels': trend_labels,
        'trend_values': trend_values,
        'weekly_buyers_counts': weekly_buyers_counts,
    })


@login_required
def vendor_profile(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        vendor = request.user.vendor
        if vendor.status != 'ACTIVE' or not request.user.is_active:
            messages.error(request, 'Your account is not approved or has been suspended.')
            return redirect('vendor_login')
    except Vendor.DoesNotExist:
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendor_login')

    if request.method == 'POST':
        form = VendorProfileForm(request.POST, instance=vendor, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('vendor_profile')
    else:
        form = VendorProfileForm(instance=vendor, user=request.user)

    return render(request, 'accounts/profile.html', {
        'vendor': vendor,
        'form': form,
    })


@login_required
def vendor_change_password(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        vendor = request.user.vendor
        if vendor.status != 'ACTIVE' or not request.user.is_active:
            messages.error(request, 'Your account is not approved or has been suspended.')
            return redirect('vendor_login')
    except Vendor.DoesNotExist:
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendor_login')

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully.')
            return redirect('vendor_change_password')
    else:
        form = PasswordChangeForm(request.user)

    for field in form.fields.values():
        existing_class = field.widget.attrs.get('class', '')
        field.widget.attrs['class'] = f"{existing_class} form-control".strip()

    return render(request, 'accounts/change_password.html', {
        'vendor': vendor,
        'form': form,
    })


# =====================================================
# FORGOT PASSWORD
# =====================================================

def password_reset_request(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email=email).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
            reset_link = f"{site_url}/reset-password/{uid}/{token}/"
            send_email(
                to_email=email,
                subject="Reset your SpotPay password",
                html=(
                    f"<p>Hello {user.username},</p>"
                    f"<p>Click the link below to reset your password:</p>"
                    f"<p><a href='{reset_link}'>{reset_link}</a></p>"
                    f"<p>This link expires in 24 hours. If you did not request this, ignore this email.</p>"
                    f"<p>SpotPay Team</p>"
                ),
                text=(
                    f"Hello {user.username},\n\nReset your password:\n{reset_link}\n\n"
                    "This link expires in 24 hours.\n\nSpotPay Team"
                ),
            )
        # always show success to avoid email enumeration
        messages.success(request, "If that email exists, a reset link has been sent.")
        return redirect('password_reset_request')
    return render(request, 'accounts/forgot_password.html')


def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        user = None

    if not user or not default_token_generator.check_token(user, token):
        messages.error(request, "This reset link is invalid or has expired.")
        return redirect('password_reset_request')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, 'accounts/reset_password.html')
        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/reset_password.html')
        user.set_password(password)
        user.save()
        messages.success(request, "Password reset successful. You can now log in.")
        return redirect('vendor_login')

    return render(request, 'accounts/reset_password.html')


# =====================================================
# VENDOR LOGOUT
# =====================================================

@login_required
def vendor_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('vendor_login')


# =====================================================
# PAY SUBSCRIPTION (UNCHANGED)
# =====================================================

@login_required
def pay_subscription(request):
    vendor = request.user.vendor

    if request.method == "POST":
        phone = request.POST.get("phone", "").strip()
        location_id = request.POST.get("location_id")

        if not phone:
            messages.error(request, "Phone number is required.")
            return redirect("vendor_dashboard")

        provider = PaymentProvider.objects.filter(is_active=True).first()
        if not provider:
            messages.error(request, "Payment service not available.")
            return redirect("vendor_dashboard")

        from hotspot.models import HotspotLocation
        from payments.utils import load_provider_adapter
        from decimal import Decimal

        location = None
        if location_id:
            location = HotspotLocation.objects.filter(id=location_id, vendor=vendor).first()

        payment = Payment.objects.create(
            payer_type="VENDOR",
            purpose="SUBSCRIPTION",
            vendor=vendor,
            location=location,
            phone=phone,
            amount=Decimal("50000"),
            provider=provider,
            currency="UGX",
        )

        try:
            adapter = load_provider_adapter(provider)
            reference = adapter.charge(payment, {"phone": phone, "amount": str(payment.amount), "currency": "UGX"})
            payment.provider_reference = reference
            payment.save(update_fields=["provider_reference"])
            messages.success(request, "Payment prompt sent. Approve on your phone.")
        except Exception as e:
            payment.delete()
            messages.error(request, f"Payment failed: {e}")

        return redirect("vendor_dashboard")

    return render(request, "payments/pay_subscription.html")


@login_required
def toggle_sms_notifications(request):
    if request.method == 'POST':
        vendor = request.user.vendor
        vendor.sms_notifications_enabled = not vendor.sms_notifications_enabled
        vendor.save(update_fields=['sms_notifications_enabled'])
        status = 'enabled' if vendor.sms_notifications_enabled else 'disabled'
        messages.success(request, f'SMS notifications {status}.')
    return redirect('vendor_profile')

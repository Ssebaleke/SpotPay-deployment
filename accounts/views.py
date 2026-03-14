from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from datetime import timedelta

from payments.models import Payment, PaymentProvider
from sms.models import VendorSMSWallet
from wallets.models import VendorWallet, WithdrawalRequest

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
            form.save()
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

            user = authenticate(username=username, password=password)

            if user is not None and user.is_active:
                if user.is_staff:
                    login(request, user)
                    return redirect('admin_dashboard')
                try:
                    vendor = user.vendor
                    if vendor.status == 'ACTIVE':
                        login(request, user)
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
    total_platform_sales = (
        Payment.objects.filter(
            purpose="TRANSACTION",
            status="SUCCESS"
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    total_vendors = Vendor.objects.count()
    active_vendors = Vendor.objects.filter(status="ACTIVE").count()

    total_transactions = Payment.objects.filter(purpose="TRANSACTION").count()
    successful_transactions = Payment.objects.filter(
        purpose="TRANSACTION",
        status="SUCCESS"
    ).count()

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

    recent_vendor_activity = Payment.objects.filter(
        purpose="TRANSACTION"
    ).select_related("vendor", "package", "location").order_by("-initiated_at")[:10]

    return render(request, 'accounts/admin_dashboard.html', {
        'total_platform_sales': total_platform_sales,
        'total_vendors': total_vendors,
        'active_vendors': active_vendors,
        'total_transactions': total_transactions,
        'successful_transactions': successful_transactions,
        'total_wallet_balance': total_wallet_balance,
        'pending_withdrawals_count': pending_withdrawals_count,
        'pending_withdrawals_total': pending_withdrawals_total,
        'pending_withdrawals': pending_withdrawals_qs.select_related('wallet', 'wallet__vendor').order_by('-created_at')[:10],
        'recent_vendor_activity': recent_vendor_activity,
    })


# =====================================================
# VENDOR DASHBOARD (REAL DATA – NO DUMMY)
# =====================================================

@login_required
def vendor_dashboard(request):
    # -------------------------------------------------
    # VALIDATE VENDOR
    # -------------------------------------------------
    try:
        vendor = request.user.vendor
        if vendor.status != 'ACTIVE' or not request.user.is_active:
            messages.error(
                request,
                'Your account is not approved or has been suspended.'
            )
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
    today = timezone.now().date()
    now = timezone.now()
    week_start = now - timezone.timedelta(days=6)
    month_start = now.replace(day=1)
    year_start = now.replace(month=1, day=1)

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
        successful_payments_qs.filter(completed_at__gte=week_start).aggregate(total=Sum("amount"))["total"]
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
    for day_offset in range(6, -1, -1):
        day = today - timedelta(days=day_offset)
        day_total = (
            successful_payments_qs.filter(completed_at__date=day).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        trend_labels.append(day.strftime("%a"))
        trend_values.append(float(day_total))

    successful_payments_count = successful_payments_qs.count()
    pending_payments_count = vendor_payments.filter(status="PENDING").count()
    failed_payments_count = vendor_payments.filter(status="FAILED").count()

    recent_transactions = vendor_payments.select_related("package").order_by("-initiated_at")[:10]

    # -------------------------------------------------
    # SMS WALLET (REAL BALANCE)
    # -------------------------------------------------
    sms_wallet = VendorSMSWallet.objects.filter(
        vendor=vendor
    ).first()

    sms_balance = sms_wallet.balance_units if sms_wallet else 0

    # -------------------------------------------------
    # DASHBOARD RENDER
    # -------------------------------------------------
    return render(request, 'accounts/dashboard.html', {
        'vendor': vendor,
        'locations_count': locations.filter(is_active=True).count(),
        'subscription_warnings': subscription_warnings,
        'sms_balance': sms_balance,   # 🔥 REAL SMS UNITS
        'total_payments_received': total_payments_received,
        'todays_payments_total': todays_payments_total,
        'weekly_payments_total': weekly_payments_total,
        'monthly_payments_total': monthly_payments_total,
        'annual_payments_total': annual_payments_total,
        'successful_payments_count': successful_payments_count,
        'pending_payments_count': pending_payments_count,
        'failed_payments_count': failed_payments_count,
        'recent_transactions': recent_transactions,
        'trend_labels': trend_labels,
        'trend_values': trend_values,
    })


@login_required
def vendor_profile(request):
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
        phone = request.POST.get("phone")

        provider = PaymentProvider.objects.filter(is_active=True).first()
        if not provider:
            messages.error(request, "Payment service not available.")
            return redirect("vendor_dashboard")

        Payment.objects.create(
            payer_type="VENDOR",
            purpose="SUBSCRIPTION",
            vendor=vendor,
            amount=Decimal("50000"),
            provider=provider,
        )

        messages.success(
            request,
            "Payment request sent. Complete the payment on your phone."
        )

        return redirect("vendor_dashboard")

    return render(request, "payments/pay_subscription.html")

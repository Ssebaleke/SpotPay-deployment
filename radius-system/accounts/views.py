from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings
import hmac
import hashlib
import time

from .models import Vendor


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("dashboard")
        messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        company_name = request.POST.get("company_name", "").strip()
        phone = request.POST.get("phone", "").strip()

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return render(request, "accounts/register.html")

        user = User.objects.create_user(username=username, email=email, password=password)
        Vendor.objects.create(user=user, company_name=company_name, phone=phone)
        login(request, user)
        messages.success(request, "Account created successfully.")
        return redirect("dashboard")

    return render(request, "accounts/register.html")


def sso_login(request):
    """
    SpotPay redirects here with a signed token for seamless login.
    URL: /sso/?token=<token>&vendor_id=<id>&ts=<timestamp>&company=<name>
    Token = HMAC-SHA256(secret, vendor_id + ts)
    """
    token = request.GET.get("token", "")
    vendor_id = request.GET.get("vendor_id", "")
    ts = request.GET.get("ts", "")
    company = request.GET.get("company", "SpotPay Vendor")

    if not token or not vendor_id or not ts:
        messages.error(request, "Invalid SSO request.")
        return redirect("login")

    # Reject tokens older than 5 minutes
    try:
        if abs(time.time() - int(ts)) > 300:
            messages.error(request, "SSO token expired.")
            return redirect("login")
    except ValueError:
        return redirect("login")

    # Verify signature
    expected = hmac.new(
        settings.SPOTPAY_SSO_SECRET.encode(),
        f"{vendor_id}{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, token):
        messages.error(request, "Invalid SSO token.")
        return redirect("login")

    # Get or create vendor account
    vendor = Vendor.objects.filter(spotpay_vendor_id=vendor_id).first()
    if not vendor:
        username = f"spotpay_{vendor_id}"
        user, _ = User.objects.get_or_create(username=username, defaults={"email": ""})
        vendor, _ = Vendor.objects.get_or_create(
            user=user,
            defaults={"company_name": company, "spotpay_vendor_id": vendor_id}
        )
    else:
        # Update company name in case it changed
        if vendor.company_name != company:
            vendor.company_name = company
            vendor.save(update_fields=["company_name"])

    login(request, vendor.user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("dashboard")

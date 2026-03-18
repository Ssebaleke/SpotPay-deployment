import random
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone

from accounts.models import Vendor
from .models import RouterConnection, VoucherProfile, VoucherBatch, MikrotikVoucher
from . import api as mt


def _get_vendor(request):
    try:
        return request.user.vendor
    except Exception:
        return None


def _vendor_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("vendor_login")
        vendor = _get_vendor(request)
        if not vendor or vendor.status != "ACTIVE":
            messages.error(request, "Access denied.")
            return redirect("vendor_login")
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _generate_code(length=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


# ─── Dashboard ───────────────────────────────────────────────────────────────

@login_required
@_vendor_required
def dashboard(request):
    vendor = _get_vendor(request)
    routers = RouterConnection.objects.filter(vendor=vendor)
    total_vouchers = MikrotikVoucher.objects.filter(batch__vendor=vendor).count()
    unused_vouchers = MikrotikVoucher.objects.filter(batch__vendor=vendor, status="UNUSED").count()
    return render(request, "mikrotik/dashboard.html", {
        "vendor": vendor,
        "routers": routers,
        "total_vouchers": total_vouchers,
        "unused_vouchers": unused_vouchers,
    })


# ─── Router Connections ───────────────────────────────────────────────────────

@login_required
@_vendor_required
def router_list(request):
    vendor = _get_vendor(request)
    routers = RouterConnection.objects.filter(vendor=vendor).select_related("location")
    return render(request, "mikrotik/router_list.html", {"vendor": vendor, "routers": routers})


@login_required
@_vendor_required
def router_add(request):
    vendor = _get_vendor(request)
    from hotspot.models import HotspotLocation
    locations = HotspotLocation.objects.filter(vendor=vendor, status="ACTIVE")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        host = request.POST.get("host", "").strip()
        port = int(request.POST.get("port", 80))
        api_username = request.POST.get("api_username", "admin").strip()
        api_password = request.POST.get("api_password", "").strip()
        location_id = request.POST.get("location_id") or None

        location = None
        if location_id:
            location = HotspotLocation.objects.filter(id=location_id, vendor=vendor).first()

        router = RouterConnection.objects.create(
            vendor=vendor, name=name, host=host, port=port,
            api_username=api_username, api_password=api_password,
            location=location,
        )
        messages.success(request, f"Router '{router.name}' added.")
        return redirect("mikrotik:router_list")

    return render(request, "mikrotik/router_form.html", {"vendor": vendor, "locations": locations})


@login_required
@_vendor_required
def router_delete(request, pk):
    vendor = _get_vendor(request)
    router = get_object_or_404(RouterConnection, pk=pk, vendor=vendor)
    if request.method == "POST":
        router.delete()
        messages.success(request, "Router removed.")
    return redirect("mikrotik:router_list")


@login_required
@_vendor_required
def router_test(request, pk):
    vendor = _get_vendor(request)
    router = get_object_or_404(RouterConnection, pk=pk, vendor=vendor)
    ok, err = mt.test_connection(router)
    if ok:
        router.last_seen = timezone.now()
        router.save(update_fields=["last_seen"])
    return JsonResponse({"ok": ok, "error": err})


# ─── Voucher Profiles ─────────────────────────────────────────────────────────

@login_required
@_vendor_required
def profile_list(request):
    vendor = _get_vendor(request)
    profiles = VoucherProfile.objects.filter(vendor=vendor).select_related("router")
    return render(request, "mikrotik/profile_list.html", {"vendor": vendor, "profiles": profiles})


@login_required
@_vendor_required
def profile_add(request):
    vendor = _get_vendor(request)
    routers = RouterConnection.objects.filter(vendor=vendor)

    if request.method == "POST":
        router_id = request.POST.get("router_id")
        router = get_object_or_404(RouterConnection, pk=router_id, vendor=vendor)
        data_limit = request.POST.get("data_limit_mb") or None
        VoucherProfile.objects.create(
            vendor=vendor,
            router=router,
            name=request.POST.get("name", "").strip(),
            price=request.POST.get("price", 0),
            validity_hours=int(request.POST.get("validity_hours", 24)),
            data_limit_mb=int(data_limit) if data_limit else None,
            shared_users=int(request.POST.get("shared_users", 1)),
        )
        messages.success(request, "Profile created.")
        return redirect("mikrotik:profile_list")

    return render(request, "mikrotik/profile_form.html", {"vendor": vendor, "routers": routers})


@login_required
@_vendor_required
def profile_edit(request, pk):
    vendor = _get_vendor(request)
    profile = get_object_or_404(VoucherProfile, pk=pk, vendor=vendor)
    routers = RouterConnection.objects.filter(vendor=vendor)

    if request.method == "POST":
        router_id = request.POST.get("router_id")
        router = get_object_or_404(RouterConnection, pk=router_id, vendor=vendor)
        data_limit = request.POST.get("data_limit_mb") or None
        profile.router = router
        profile.name = request.POST.get("name", "").strip()
        profile.price = request.POST.get("price", 0)
        profile.validity_hours = int(request.POST.get("validity_hours", 24))
        profile.data_limit_mb = int(data_limit) if data_limit else None
        profile.shared_users = int(request.POST.get("shared_users", 1))
        profile.save()
        messages.success(request, "Profile updated.")
        return redirect("mikrotik:profile_list")

    return render(request, "mikrotik/profile_form.html", {
        "vendor": vendor, "routers": routers, "profile": profile
    })


@login_required
@_vendor_required
def profile_delete(request, pk):
    vendor = _get_vendor(request)
    profile = get_object_or_404(VoucherProfile, pk=pk, vendor=vendor)
    if request.method == "POST":
        profile.delete()
        messages.success(request, "Profile deleted.")
    return redirect("mikrotik:profile_list")


# ─── Generate Vouchers ────────────────────────────────────────────────────────

@login_required
@_vendor_required
def generate(request):
    vendor = _get_vendor(request)
    profiles = VoucherProfile.objects.filter(vendor=vendor, is_active=True).select_related("router")

    if request.method == "POST":
        profile_id = request.POST.get("profile_id")
        quantity = int(request.POST.get("quantity", 10))
        quantity = min(quantity, 500)  # cap at 500

        profile = get_object_or_404(VoucherProfile, pk=profile_id, vendor=vendor)
        router = profile.router

        batch = VoucherBatch.objects.create(
            vendor=vendor, router=router, profile=profile, quantity=quantity
        )

        # Build limit-uptime string e.g. "24:00:00"
        h = profile.validity_hours
        limit_uptime = f"{h:02d}:00:00"
        limit_bytes = (profile.data_limit_mb * 1024 * 1024) if profile.data_limit_mb else None

        pushed, failed = 0, 0
        for _ in range(quantity):
            # ensure unique code
            for attempt in range(10):
                code = _generate_code()
                if not MikrotikVoucher.objects.filter(code=code).exists():
                    break

            ok, err = mt.add_hotspot_user(router, code, profile.name, limit_uptime, limit_bytes)
            MikrotikVoucher.objects.create(
                batch=batch, code=code,
                pushed_to_router=ok,
                push_error="" if ok else (err or ""),
            )
            if ok:
                pushed += 1
            else:
                failed += 1

        if failed == 0:
            messages.success(request, f"{pushed} vouchers generated and pushed to router.")
        else:
            messages.warning(
                request,
                f"{pushed} pushed successfully, {failed} failed (router unreachable or error). "
                "Vouchers saved — you can retry push later."
            )
        return redirect("mikrotik:batch_list")

    return render(request, "mikrotik/generate.html", {"vendor": vendor, "profiles": profiles})


# ─── Batches & Print ─────────────────────────────────────────────────────────

@login_required
@_vendor_required
def batch_list(request):
    vendor = _get_vendor(request)
    batches = VoucherBatch.objects.filter(vendor=vendor).select_related("profile", "router")
    return render(request, "mikrotik/batch_list.html", {"vendor": vendor, "batches": batches})


@login_required
@_vendor_required
def batch_print(request, uuid):
    vendor = _get_vendor(request)
    batch = get_object_or_404(VoucherBatch, uuid=uuid, vendor=vendor)
    vouchers = batch.vouchers.filter(status="UNUSED")
    return render(request, "mikrotik/print.html", {
        "batch": batch,
        "vouchers": vouchers,
    })


# ─── Active Sessions ──────────────────────────────────────────────────────────

@login_required
@_vendor_required
def sessions(request, router_pk):
    vendor = _get_vendor(request)
    router = get_object_or_404(RouterConnection, pk=router_pk, vendor=vendor)
    active, err = mt.get_active_sessions(router)
    return render(request, "mikrotik/sessions.html", {
        "vendor": vendor,
        "router": router,
        "sessions": active,
        "error": err,
    })

import io
import csv
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db import transaction

from accounts.models import Vendor
from .models import NasDevice, Profile, VoucherBatch, Voucher, RadiusSession
from . import freeradius as fr

logger = logging.getLogger(__name__)


def _vendor(request):
    try:
        return request.user.vendor
    except Exception:
        return None


def _require_vendor(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not _vendor(request):
            messages.error(request, "Vendor account required.")
            return redirect("login")
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ─── Dashboard ───────────────────────────────────────────────────────────────

@login_required
@_require_vendor
def dashboard(request):
    vendor = _vendor(request)
    total_vouchers = Voucher.objects.filter(batch__vendor=vendor).count()
    unused_vouchers = Voucher.objects.filter(batch__vendor=vendor, status="UNUSED").count()
    used_vouchers = Voucher.objects.filter(batch__vendor=vendor, status="USED").count()
    profiles = Profile.objects.filter(vendor=vendor, is_active=True).count()
    nas_devices = NasDevice.objects.filter(vendor=vendor, is_active=True).count()

    # Active sessions from FreeRADIUS
    usernames = list(Voucher.objects.filter(
        batch__vendor=vendor, status="USED"
    ).values_list("code", flat=True)[:500])
    active_sessions = fr.get_active_sessions(usernames)

    return render(request, "radius/dashboard.html", {
        "vendor": vendor,
        "total_vouchers": total_vouchers,
        "unused_vouchers": unused_vouchers,
        "used_vouchers": used_vouchers,
        "profiles_count": profiles,
        "nas_count": nas_devices,
        "active_sessions": active_sessions[:10],
        "active_count": len(active_sessions),
    })


# ─── NAS Devices ─────────────────────────────────────────────────────────────

@login_required
@_require_vendor
def nas_list(request):
    vendor = _vendor(request)
    devices = NasDevice.objects.filter(vendor=vendor).order_by("-created_at")
    return render(request, "radius/nas_list.html", {"vendor": vendor, "devices": devices})


@login_required
@_require_vendor
def nas_add(request):
    vendor = _vendor(request)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        nas_ip = request.POST.get("nas_ip", "").strip()
        shared_secret = request.POST.get("shared_secret", "").strip()
        description = request.POST.get("description", "").strip()

        if not name or not nas_ip or not shared_secret:
            messages.error(request, "Name, IP and shared secret are required.")
            return render(request, "radius/nas_form.html", {"vendor": vendor})

        NasDevice.objects.create(
            vendor=vendor, name=name, nas_ip=nas_ip,
            shared_secret=shared_secret, description=description
        )
        messages.success(request, f"Router '{name}' added successfully.")
        return redirect("nas_list")

    return render(request, "radius/nas_form.html", {"vendor": vendor})


@login_required
@_require_vendor
def nas_delete(request, pk):
    vendor = _vendor(request)
    device = get_object_or_404(NasDevice, pk=pk, vendor=vendor)
    if request.method == "POST":
        fr.delete_nas(device.nas_ip)
        device.delete()
        messages.success(request, "Router removed.")
    return redirect("nas_list")


# ─── Profiles ─────────────────────────────────────────────────────────────────

@login_required
@_require_vendor
def profile_list(request):
    vendor = _vendor(request)
    profiles = Profile.objects.filter(vendor=vendor).order_by("name")
    return render(request, "radius/profile_list.html", {"vendor": vendor, "profiles": profiles})


@login_required
@_require_vendor
def profile_add(request):
    vendor = _vendor(request)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        session_timeout = int(request.POST.get("session_timeout", 0) or 0)
        data_limit_mb = int(request.POST.get("data_limit_mb", 0) or 0)
        download_kbps = int(request.POST.get("download_kbps", 0) or 0)
        upload_kbps = int(request.POST.get("upload_kbps", 0) or 0)
        simultaneous_use = int(request.POST.get("simultaneous_use", 1) or 1)

        if not name:
            messages.error(request, "Profile name is required.")
            return render(request, "radius/profile_form.html", {"vendor": vendor})

        if Profile.objects.filter(vendor=vendor, name=name).exists():
            messages.error(request, "A profile with this name already exists.")
            return render(request, "radius/profile_form.html", {"vendor": vendor})

        profile = Profile.objects.create(
            vendor=vendor, name=name,
            session_timeout=session_timeout,
            data_limit_mb=data_limit_mb,
            download_kbps=download_kbps,
            upload_kbps=upload_kbps,
            simultaneous_use=simultaneous_use,
        )
        fr.sync_profile(profile)
        messages.success(request, f"Profile '{name}' created.")
        return redirect("profile_list")

    return render(request, "radius/profile_form.html", {"vendor": vendor})


@login_required
@_require_vendor
def profile_edit(request, pk):
    vendor = _vendor(request)
    profile = get_object_or_404(Profile, pk=pk, vendor=vendor)

    if request.method == "POST":
        profile.session_timeout = int(request.POST.get("session_timeout", 0) or 0)
        profile.data_limit_mb = int(request.POST.get("data_limit_mb", 0) or 0)
        profile.download_kbps = int(request.POST.get("download_kbps", 0) or 0)
        profile.upload_kbps = int(request.POST.get("upload_kbps", 0) or 0)
        profile.simultaneous_use = int(request.POST.get("simultaneous_use", 1) or 1)
        profile.save()
        fr.sync_profile(profile)
        messages.success(request, f"Profile '{profile.name}' updated.")
        return redirect("profile_list")

    return render(request, "radius/profile_form.html", {"vendor": vendor, "profile": profile})


@login_required
@_require_vendor
def profile_delete(request, pk):
    vendor = _vendor(request)
    profile = get_object_or_404(Profile, pk=pk, vendor=vendor)
    if request.method == "POST":
        fr.delete_profile(profile)
        profile.delete()
        messages.success(request, "Profile deleted.")
    return redirect("profile_list")


# ─── Voucher Generation ───────────────────────────────────────────────────────

@login_required
@_require_vendor
def voucher_generate(request):
    vendor = _vendor(request)
    profiles = Profile.objects.filter(vendor=vendor, is_active=True)

    if request.method == "POST":
        profile_id = request.POST.get("profile_id")
        quantity = min(int(request.POST.get("quantity", 10) or 10), 1000)
        profile = get_object_or_404(Profile, pk=profile_id, vendor=vendor)

        with transaction.atomic():
            batch = VoucherBatch.objects.create(
                vendor=vendor, profile=profile, quantity=quantity
            )
            vouchers = []
            existing_codes = set(Voucher.objects.values_list("code", flat=True))

            for _ in range(quantity):
                for _ in range(20):
                    code = Voucher.generate_code()
                    if code not in existing_codes:
                        existing_codes.add(code)
                        break
                vouchers.append(Voucher(batch=batch, code=code))

            Voucher.objects.bulk_create(vouchers)

        # Push all to FreeRADIUS in one transaction
        fr.bulk_add_vouchers(vouchers)

        messages.success(request, f"{quantity} vouchers generated successfully.")
        return redirect("batch_detail", uuid=batch.uuid)

    return render(request, "radius/voucher_generate.html", {
        "vendor": vendor,
        "profiles": profiles,
    })


@login_required
@_require_vendor
def batch_list(request):
    vendor = _vendor(request)
    batches = VoucherBatch.objects.filter(vendor=vendor).select_related("profile")
    return render(request, "radius/batch_list.html", {"vendor": vendor, "batches": batches})


@login_required
@_require_vendor
def batch_detail(request, uuid):
    vendor = _vendor(request)
    batch = get_object_or_404(VoucherBatch, uuid=uuid, vendor=vendor)
    vouchers = batch.vouchers.all()
    return render(request, "radius/batch_detail.html", {
        "vendor": vendor,
        "batch": batch,
        "vouchers": vouchers,
    })


@login_required
@_require_vendor
def batch_delete(request, uuid):
    vendor = _vendor(request)
    batch = get_object_or_404(VoucherBatch, uuid=uuid, vendor=vendor)
    if request.method == "POST":
        # Remove from FreeRADIUS
        codes = list(batch.vouchers.values_list("code", flat=True))
        for code in codes:
            fr.disable_voucher(code)
        batch.delete()
        messages.success(request, "Batch deleted.")
    return redirect("batch_list")


# ─── Export ───────────────────────────────────────────────────────────────────

@login_required
@_require_vendor
def export_csv(request, uuid):
    vendor = _vendor(request)
    batch = get_object_or_404(VoucherBatch, uuid=uuid, vendor=vendor)
    vouchers = batch.vouchers.filter(status="UNUSED")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="vouchers-{batch.uuid}.csv"'

    writer = csv.writer(response)
    writer.writerow(["Code", "Profile", "Status", "Created"])
    for v in vouchers:
        writer.writerow([v.code, batch.profile.name, v.status, v.created_at.strftime("%Y-%m-%d %H:%M")])

    return response


@login_required
@_require_vendor
def export_pdf(request, uuid):
    vendor = _vendor(request)
    batch = get_object_or_404(VoucherBatch, uuid=uuid, vendor=vendor)
    vouchers = batch.vouchers.filter(status="UNUSED")

    return render(request, "radius/voucher_print.html", {
        "vendor": vendor,
        "batch": batch,
        "vouchers": vouchers,
        "profile": batch.profile,
    })


# ─── Sessions ─────────────────────────────────────────────────────────────────

@login_required
@_require_vendor
def sessions_view(request):
    vendor = _vendor(request)
    usernames = list(Voucher.objects.filter(
        batch__vendor=vendor
    ).values_list("code", flat=True))

    active = fr.get_active_sessions(usernames)
    history = fr.get_session_history(usernames, limit=50)

    return render(request, "radius/sessions.html", {
        "vendor": vendor,
        "active_sessions": active,
        "history": history,
    })


# ─── Voucher Disable ──────────────────────────────────────────────────────────

@login_required
@_require_vendor
def voucher_disable(request, pk):
    vendor = _vendor(request)
    voucher = get_object_or_404(Voucher, pk=pk, batch__vendor=vendor)
    if request.method == "POST":
        fr.disable_voucher(voucher.code)
        voucher.status = Voucher.STATUS_DISABLED
        voucher.save(update_fields=["status"])
        messages.success(request, f"Voucher {voucher.code} disabled.")
    return redirect("batch_detail", uuid=voucher.batch.uuid)


# ─── MikroTik Config Script ───────────────────────────────────────────────────

@login_required
@_require_vendor
def mikrotik_config(request, pk):
    """Generate MikroTik RADIUS client configuration script."""
    vendor = _vendor(request)
    device = get_object_or_404(NasDevice, pk=pk, vendor=vendor)
    from django.conf import settings
    vps_ip = settings.VPS_IP if hasattr(settings, "VPS_IP") else "68.168.222.37"

    script = f"""# SpotPay RADIUS Configuration for {device.name}
# Run this in MikroTik Terminal

# Add RADIUS server
/radius add service=hotspot address={vps_ip} secret="{device.shared_secret}" authentication-port=1812 accounting-port=1813 comment="SpotPay RADIUS"

# Enable RADIUS for hotspot
/ip hotspot profile set [find] use-radius=yes

# Enable RADIUS accounting
/radius incoming set accept=yes

:put "SpotPay RADIUS configured successfully"
"""
    return HttpResponse(script, content_type="text/plain")

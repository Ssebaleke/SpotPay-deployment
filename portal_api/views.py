from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from pathlib import Path
import zipfile
import io
import tempfile
import json
import textwrap

from hotspot.models import HotspotLocation
from portal_api.models import PortalTemplate
from packages.models import Package
from payments.services_utils import initiate_payment
from payments.models import Payment


# =====================================================
# PORTAL DATA API (used by portal.js)
# GET  /api/portal/<uuid>/
# =====================================================

def portal_data(request, uuid):
    location = get_object_or_404(
        HotspotLocation,
        uuid=uuid,
        status="ACTIVE",
        vendor__status="ACTIVE"
    )

    packages = location.packages.filter(
        is_active=True,
        vouchers__status='UNUSED'
    ).distinct()

    ads = location.ads.filter(is_active=True)

    return JsonResponse({
        "location": {
            "name": location.site_name,
        },
        "packages": [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
            }
            for p in packages
        ],
        "ads": [
            {
                "type": ad.ad_type.lower(),
                "url": request.build_absolute_uri(ad.file.url),
            }
            for ad in ads
        ],
    })


# =====================================================
# JS BUY API (used by portal.js Buy button)
# POST /api/portal/<uuid>/buy/
# Body JSON: { "package_id": 1, "phone": "2567xxxxxxx", "mac_address": "", "ip_address": "" }
# =====================================================

@csrf_exempt
@require_POST
def portal_buy_api(request, uuid):
    location = get_object_or_404(
        HotspotLocation,
        uuid=uuid,
        status="ACTIVE",
        vendor__status="ACTIVE"
    )

    # 🔒 enforce subscription
    if not location.has_active_subscription():
        return JsonResponse(
            {"success": False, "message": "SpotPay services unavailable for this location"},
            status=403
        )

    # parse JSON safely
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    package_id = payload.get("package_id")
    phone = (payload.get("phone") or "").strip()
    mac_address = (payload.get("mac_address") or "").strip() or None
    ip_address = (payload.get("ip_address") or "").strip() or None

    if not package_id or not phone:
        return JsonResponse(
            {"success": False, "message": "Please select a package and enter a phone number"},
            status=400
        )

    # Get package by ID
    package = get_object_or_404(
        Package,
        id=package_id,
        location=location,
        is_active=True
    )

    # Ensure vouchers exist
    if not package.vouchers.filter(status="UNUSED").exists():
        return JsonResponse(
            {"success": False, "message": "This package is currently out of stock"},
            status=400
        )

    # ✅ initiate payment (your existing engine)
    try:
        result = initiate_payment(
            location=location,
            package=package,
            phone=phone,
            source="JS_PORTAL",
            mac_address=mac_address,
            ip_address=ip_address,
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "message": str(e)},
            status=400
        )

    if result.get("status_url") and not result["status_url"].startswith("http"):
        result["status_url"] = request.build_absolute_uri(result["status_url"])

    return JsonResponse(result)


# =====================================================
# DOWNLOAD PORTAL ZIP (Vendor)
# =====================================================

def download_portal_zip(request, location_uuid):
    location = get_object_or_404(
        HotspotLocation,
        uuid=location_uuid,
        status="ACTIVE",
        vendor__status="ACTIVE"
    )

    template = get_object_or_404(PortalTemplate, is_active=True)

    # --- Single file mode: ?file=login.html or ?file=js/portal.js ---
    file_param = request.GET.get("file", "").strip().lstrip("/")
    if file_param:
        with zipfile.ZipFile(template.zip_file.path, "r") as zf:
            # find the entry — may be stored as hotspot/login.html or just login.html
            names = zf.namelist()
            match = None
            for n in names:
                parts = n.split("/")
                rel = "/".join(parts[1:]) if len(parts) > 1 else parts[0]
                if rel == file_param:
                    match = n
                    break
            if not match:
                from django.http import Http404
                raise Http404

            content = zf.read(match)
            ext = Path(file_param).suffix
            if ext in [".html", ".js", ".css"]:
                text = content.decode("utf-8", errors="ignore")
                text = text.replace("{{API_BASE}}", settings.PORTAL_API_BASE)
                text = text.replace("{{LOCATION_UUID}}", str(location.uuid))
                text = text.replace("{{BUY_URL}}", f"{settings.SITE_URL}/api/portal/{location.uuid}/buy/")
                text = text.replace("{{SUPPORT_PHONE}}", getattr(location.vendor, "business_phone", "") or "")
                content = text.encode("utf-8")

            content_types = {
                ".html": "text/html", ".js": "application/javascript",
                ".css": "text/css", ".png": "image/png",
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".ico": "image/x-icon",
            }
            ct = content_types.get(ext, "application/octet-stream")
            resp = HttpResponse(content, content_type=ct)
            resp["Content-Disposition"] = f'inline; filename="{Path(file_param).name}"'
            return resp

    # --- Full ZIP mode ---
    buffer = io.BytesIO()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        with zipfile.ZipFile(template.zip_file.path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for file_path in tmpdir.rglob("*"):
                if file_path.is_dir():
                    continue

                arcname = file_path.relative_to(tmpdir)
                content = file_path.read_bytes()

                if file_path.suffix in [".html", ".js", ".css"]:
                    text = content.decode("utf-8", errors="ignore")
                    text = text.replace("{{API_BASE}}", settings.PORTAL_API_BASE)
                    text = text.replace("{{LOCATION_UUID}}", str(location.uuid))
                    text = text.replace("{{BUY_URL}}", f"{settings.SITE_URL}/api/portal/{location.uuid}/buy/")
                    text = text.replace("{{SUPPORT_PHONE}}", getattr(location.vendor, "business_phone", "") or "")
                    zip_out.writestr(str(arcname), text)
                else:
                    zip_out.writestr(str(arcname), content)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="hotspot-{location.site_name}.zip"'
    return response


# =====================================================
# VENDOR PORTAL PAGES
# =====================================================

@login_required
def portal_download_page(request, location_uuid):
    vendor = request.user.vendor

    location = get_object_or_404(
        vendor.locations,
        uuid=location_uuid,
        status="ACTIVE"
    )

    return render(
        request,
        "portal_api/portal_download.html",
        {
            "location": location,
            "site_url": settings.SITE_URL,
        }
    )


# =====================================================
# MIKROTIK SETUP SCRIPT
# GET /api/portal/<uuid>/mikrotik-script/
# Returns a plain-text RouterOS script the vendor
# pastes into MikroTik Terminal to:
#   1. Add walled-garden rules for SpotPay server
#   2. Download all hotspot portal files via /tool fetch
# =====================================================

@login_required
def mikrotik_setup_script(request, location_uuid):
    vendor = request.user.vendor

    location = get_object_or_404(
        vendor.locations,
        uuid=location_uuid,
        status="ACTIVE"
    )

    from urllib.parse import urlparse
    import socket
    parsed = urlparse(settings.SITE_URL)
    server_host = parsed.hostname or settings.SITE_URL

    # Resolve IP for walled-garden ip rule
    try:
        server_ip = socket.gethostbyname(server_host)
    except Exception:
        server_ip = server_host

    zip_url = f"{settings.SITE_URL}/api/portal/{location.uuid}/download/"
    dns_name = location.hotspot_dns or "hot.spot"

    # Build per-file fetch commands by inspecting the active ZIP template
    file_fetch_lines = []
    try:
        from portal_api.models import PortalTemplate
        template = PortalTemplate.objects.filter(is_active=True).first()
        if template and template.zip_file:
            with zipfile.ZipFile(template.zip_file.path, "r") as zf:
                for name in zf.namelist():
                    if name.endswith("/"):
                        continue
                    # strip any leading folder from zip (e.g. hotspot/login.html -> login.html)
                    parts = name.split("/")
                    rel = "/".join(parts[1:]) if len(parts) > 1 else parts[0]
                    if not rel:
                        continue
                    file_url = f"{settings.SITE_URL}/api/portal/{location.uuid}/download/?file={rel}"
                    dst = f"hotspot/{rel}"
                    file_fetch_lines.append(f"/tool fetch url=""{file_url}"" dst-path=""{dst}"" mode=https")
    except Exception:
        pass

    # Fallback: just fetch the zip and instruct manual extraction
    if not file_fetch_lines:
        file_fetch_lines = [
            f"/tool fetch url=""{zip_url}"" dst-path=\"flash/hotspot-spotpay.zip\" mode=https",
            "# Extract the ZIP manually via Winbox: Files -> right-click -> Extract",
            "# Then move all extracted files into the hotspot folder",
        ]

    fetch_block = "\r\n".join(file_fetch_lines)

    script = (
        f"# =======================================================\r\n"
        f"# SpotPay MikroTik Setup Script\r\n"
        f"# Location : {location.site_name}\r\n"
        f"# Paste this entire script into MikroTik Terminal\r\n"
        f"# =======================================================\r\n"
        f"\r\n"
        f"# --- 1. Walled Garden IP (allow by IP address) ---\r\n"
        f"/ip hotspot walled-garden ip\r\n"
        f"add action=accept comment=\"SpotPay Server\" dst-address={server_ip}\r\n"
        f"\r\n"
        f"# --- 2. Walled Garden Host (allow by domain) ---\r\n"
        f"/ip hotspot walled-garden\r\n"
        f"add action=allow comment=\"SpotPay API\" dst-host={server_host}\r\n"
        f"\r\n"
        f"# --- 3. Download portal files into hotspot folder ---\r\n"
        f"{fetch_block}\r\n"
        f"\r\n"
        f"# --- 4. Confirm hotspot DNS name ---\r\n"
        f"# Go to: IP -> Hotspot -> Server Profiles -> DNS Name\r\n"
        f"# Make sure it is set to: {dns_name}\r\n"
        f"\r\n"
        f":log info \"SpotPay portal setup complete for {location.site_name}\"\r\n"
        f":put \"Done. Hotspot portal files installed.\"\r\n"
    )

    return HttpResponse(script, content_type="text/plain; charset=utf-8")


@login_required
def location_portal_view(request, uuid):
    vendor = request.user.vendor

    location = get_object_or_404(
        HotspotLocation,
        uuid=uuid,
        vendor=vendor
    )

    return render(
        request,
        "portal_api/location_portal.html",
        {"location": location}
    )


# =====================================================
# FALLBACK / ALTERNATIVE BUY PAGE (NO JS)
# (keep as-is, but now we capture the returned dict)
# =====================================================

def portal_buy(request, uuid):
    """
    Fallback voucher purchase page.
    Server-rendered. Walled-garden safe.
    """
    location = get_object_or_404(
        HotspotLocation,
        uuid=uuid,
        status="ACTIVE"
    )

    if not location.has_active_subscription():
        return HttpResponseForbidden("SpotPay services unavailable for this location")

    if request.method == "GET":
        packages = Package.objects.filter(
            location=location,
            is_active=True,
            vouchers__status="UNUSED"
        ).distinct()

        return render(
            request,
            "portal_api/buy.html",
            {"location": location, "packages": packages}
        )

    if request.method == "POST":
        package_id = request.POST.get("package")
        phone = request.POST.get("phone")

        packages = Package.objects.filter(
            location=location,
            is_active=True,
            vouchers__status="UNUSED"
        ).distinct()

        if not package_id or not phone:
            return render(
                request,
                "portal_api/buy.html",
                {
                    "location": location,
                    "packages": packages,
                    "error": "Please select a package and enter a phone number",
                }
            )

        package = get_object_or_404(
            Package,
            id=package_id,
            location=location,
            is_active=True
        )

        if not package.vouchers.filter(status="UNUSED").exists():
            return render(
                request,
                "portal_api/buy.html",
                {
                    "location": location,
                    "packages": packages,
                    "error": "This package is currently out of stock",
                }
            )

        result = initiate_payment(
            location=location,
            package=package,
            phone=phone,
            source="FALLBACK_PORTAL",
        )

        return render(
            request,
            "portal_api/buy_processing.html",
            {
                "location": location,
                "package": package,
                "phone": phone,
                "payment": result,  # ✅ use status_url / reference in template
            }
        )
        
        
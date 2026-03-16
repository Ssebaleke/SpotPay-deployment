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

    # ✅ Show ONLY packages that still have UNUSED vouchers
    packages = location.packages.filter(
        is_active=True,
        vouchers__status="UNUSED"
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
                "type": ad.ad_type,
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

    # Ensure status_url is absolute for captive portal
    if result.get("status_url"):
        result["status_url"] = request.build_absolute_uri(result["status_url"])

    return JsonResponse(result)


# =====================================================
# STATUS API (polling)
# If you ALREADY have /payments/status/<reference>/ in payments app,
# you can skip this and just poll that existing endpoint.
# But this is a safe fallback.
# GET /api/portal/payments/status/<reference>/
# =====================================================

def portal_payment_status(request, reference):
    payment = get_object_or_404(Payment, provider_reference=reference)

    voucher = None
    try:
        voucher = payment.issued_voucher.voucher.code
    except Exception:
        voucher = None

    return JsonResponse({
        "success": True,
        "status": payment.status,
        "message": (
            "Please approve the payment on your phone."
            if payment.status == "PENDING"
            else "Payment successful."
            if payment.status == "SUCCESS"
            else "Payment failed."
        ),
        "voucher": voucher,
    })


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
                    text = text.replace(
                        "{{SUPPORT_PHONE}}",
                        getattr(location.vendor, "business_phone", "") or ""
                    )
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

    # Parse host from SITE_URL  e.g. "69.164.245.17" or "spotpay.example.com"
    from urllib.parse import urlparse
    parsed = urlparse(settings.SITE_URL)
    server_host = parsed.hostname or settings.SITE_URL

    zip_url = f"{settings.SITE_URL}/api/portal/{location.uuid}/download/"
    dns_name = location.hotspot_dns or "hot.spot"

    script = textwrap.dedent(f"""\
        # =======================================================
        # SpotPay MikroTik Setup Script
        # Location : {location.site_name}
        # Generated: auto
        # Paste this entire script into MikroTik Terminal
        # =======================================================

        # --- 1. Walled Garden: allow SpotPay server ---
        /ip hotspot walled-garden ip
        add action=accept comment="SpotPay Server" dst-host={server_host}

        /ip hotspot walled-garden
        add action=allow comment="SpotPay API" dst-host={server_host}

        # --- 2. Download portal files to MikroTik ---
        /tool fetch url="{zip_url}" dst-path="hotspot-spotpay.zip"

        # --- 3. Extract ZIP into hotspot folder ---
        /file
        :local zipName "hotspot-spotpay.zip"
        :local destDir "hotspot"
        /tool fetch url="{zip_url}" dst-path=($destDir . "/hotspot-spotpay.zip")

        # Note: RouterOS 7.x supports ZIP extraction natively.
        # If on RouterOS 6.x, extract on your PC and upload via
        # Winbox Files or FTP, then skip step 3.

        # --- 4. Confirm DNS name matches this script ---
        # Your MikroTik hotspot DNS name must be set to:
        #   {dns_name}
        # Go to: IP -> Hotspot -> Server Profiles -> DNS Name

        :log info "SpotPay portal setup complete for {location.site_name}"
        :put "Done. Reload hotspot to apply changes."
    """)

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
        
        
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required

from pathlib import Path
import zipfile
import io
import tempfile

from hotspot.models import HotspotLocation
from portal_api.models import PortalTemplate
from packages.models import Package
from payments.services_utils import initiate_payment


# =====================================================
# PORTAL DATA API (used by portal.js)
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
                "type": ad.ad_type,
                "url": request.build_absolute_uri(ad.file.url),
            }
            for ad in ads
        ],
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
                    text = content.decode("utf-8")
                    text = text.replace("{{API_BASE}}", settings.PORTAL_API_BASE)
                    text = text.replace("{{LOCATION_UUID}}", str(location.uuid))
                    text = text.replace(
                        "{{SUPPORT_PHONE}}",
                        getattr(location.vendor, "support_phone", "")
                    )
                    zip_out.writestr(str(arcname), text)
                else:
                    zip_out.writestr(str(arcname), content)

    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/zip")
    response["Content-Disposition"] = (
        f'attachment; filename="hotspot-{location.site_name}.zip"'
    )
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
        {"location": location}
    )


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

    # 🔒 ENFORCE SUBSCRIPTION
    if not location.has_active_subscription():
        return HttpResponseForbidden(
            "SpotPay services unavailable for this location"
        )

    # ----------------------
    # GET → SHOW PACKAGES
    # ----------------------
    if request.method == "GET":
        packages = Package.objects.filter(
            location=location,
            is_active=True,
            vouchers__status='UNUSED'
        ).distinct()

        return render(
            request,
            "portal_api/buy.html",
            {
                "location": location,
                "packages": packages,
            }
        )

    # ----------------------
    # POST → INITIATE PAYMENT
    # ----------------------
    if request.method == "POST":
        package_id = request.POST.get("package")
        phone = request.POST.get("phone")

        packages = Package.objects.filter(
            location=location,
            is_active=True,
            vouchers__status='UNUSED'
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

        # 🔐 Step 1: Get package by ID ONLY (no joins)
        package = get_object_or_404(
            Package,
            id=package_id,
            location=location,
            is_active=True
        )

        # 🔐 Step 2: Ensure vouchers still exist
        if not package.vouchers.filter(status='UNUSED').exists():
            return render(
                request,
                "portal_api/buy.html",
                {
                    "location": location,
                    "packages": packages,
                    "error": "This package is currently out of stock",
                }
            )

        # ✅ Safe to initiate payment
        initiate_payment(
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
            }
        )

from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from hotspot.models import HotspotLocation
from portal_api.models import PortalTemplate
import zipfile
import io
import tempfile
from pathlib import Path
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from hotspot.models import HotspotLocation




def portal_data(request, uuid):
    """
    API consumed by portal.js
    Provides location name, packages, and ads
    """
    location = get_object_or_404(
        HotspotLocation,
        uuid=uuid,
        status="ACTIVE",
        vendor__status="ACTIVE"
    )

    packages = location.packages.filter(is_active=True)
    ads = location.ads.filter(is_active=True)

    return JsonResponse({
        "location": {
            "name": location.site_name
        },
        "packages": [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price
            }
            for p in packages
        ],
        "ads": [
            {
                "type": ad.ad_type,
                "url": request.build_absolute_uri(ad.file.url)
            }
            for ad in ads
        ]
    })


def download_portal_zip(request, location_uuid):
    """
    Generates a MikroTik captive portal ZIP from the
    admin-uploaded portal template
    """
    location = get_object_or_404(
        HotspotLocation,
        uuid=location_uuid,
        status="ACTIVE",
        vendor__status="ACTIVE"
    )

    template = get_object_or_404(
        PortalTemplate,
        is_active=True
    )

    buffer = io.BytesIO()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Extract uploaded template ZIP
        with zipfile.ZipFile(template.zip_file.path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        # Rebuild ZIP with injected values
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

    return render(request, "portal_api/location_portal.html", {
        "location": location
    })

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.exceptions import ValidationError

from .models import HotspotLocation
from .forms import HotspotLocationForm


# =====================================================
# LIST LOCATIONS
# =====================================================

@login_required
def locations_list(request):
    vendor = request.user.vendor
    locations = vendor.locations.all().order_by('-created_at')

    return render(request, 'hotspot/locations.html', {
        'locations': locations,
        'vendor': vendor
    })


# =====================================================
# ADD LOCATION
# =====================================================

@login_required
def add_location(request):
    if request.method == 'POST':
        form = HotspotLocationForm(request.POST)

        if form.is_valid():
            location = form.save(commit=False)
            location.vendor = request.user.vendor

            if not location.hotspot_dns:
                location.hotspot_dns = "hot.spot"

            location.save()

            messages.success(
                request,
                f'Location "{location.site_name}" submitted for approval.'
            )

        return redirect('locations_list')

    return redirect('locations_list')


# =====================================================
# EDIT LOCATION (DNS ONLY)
# =====================================================

@login_required
def edit_location(request, location_id):
    vendor = request.user.vendor

    location = get_object_or_404(
        HotspotLocation,
        id=location_id,
        vendor=vendor
    )

    if request.method == "POST":
        hotspot_dns = request.POST.get("hotspot_dns", "hot.spot").strip()
        location.hotspot_dns = hotspot_dns
        location.save(update_fields=["hotspot_dns"])

        messages.success(request, "Hotspot DNS updated successfully.")
        return redirect("locations_list")

    return render(
        request,
        "hotspot/location_form.html",
        {"location": location}
    )


# =====================================================
# LOCATION STATUS (AJAX)
# =====================================================

@login_required
def location_status(request, location_id):
    vendor = request.user.vendor

    location = get_object_or_404(
        HotspotLocation,
        id=location_id,
        vendor=vendor
    )

    return JsonResponse({
        'status': location.status,
        'status_display': location.get_status_display(),
        'portal_url': location.portal_url or '',
        'location_uuid': str(location.uuid),
        'rejection_reason': location.rejection_reason or '',
    })

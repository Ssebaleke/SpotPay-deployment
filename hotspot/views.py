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
    # Allow staff to view first vendor's locations for testing
    if request.user.is_staff:
        from accounts.models import Vendor
        vendor = Vendor.objects.filter(status='ACTIVE').first()
        if not vendor:
            messages.error(request, 'No active vendors in the system.')
            return redirect('admin_dashboard')
    else:
        try:
            vendor = request.user.vendor
        except:
            messages.error(request, 'You are not registered as a vendor.')
            return redirect('vendor_login')
    
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
    # Staff users cannot add locations
    if request.user.is_staff:
        messages.warning(request, 'Staff users cannot add locations.')
        return redirect('locations_list')
    
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
    # Allow staff to view first vendor's locations for testing
    if request.user.is_staff:
        from accounts.models import Vendor
        vendor = Vendor.objects.filter(status='ACTIVE').first()
        if not vendor:
            messages.error(request, 'No active vendors in the system.')
            return redirect('admin_dashboard')
    else:
        try:
            vendor = request.user.vendor
        except:
            messages.error(request, 'You are not registered as a vendor.')
            return redirect('vendor_login')

    location = get_object_or_404(
        HotspotLocation,
        id=location_id,
        vendor=vendor
    )

    if request.method == "POST":
        # Staff users cannot edit locations
        if request.user.is_staff:
            messages.warning(request, 'Staff users cannot edit locations.')
            return redirect('locations_list')
        
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
    # Allow staff to view first vendor's locations for testing
    if request.user.is_staff:
        from accounts.models import Vendor
        vendor = Vendor.objects.filter(status='ACTIVE').first()
        if not vendor:
            return JsonResponse({'error': 'No active vendors'}, status=404)
    else:
        try:
            vendor = request.user.vendor
        except:
            return JsonResponse({'error': 'Not a vendor'}, status=403)

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

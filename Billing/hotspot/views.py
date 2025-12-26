# hotspot/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.exceptions import ValidationError

from .models import HotspotLocation
from .forms import HotspotLocationForm

# 🔑 PAYMENT LAYER
from payments.models import create_default_location_billing

@login_required
def locations_list(request):
    """
    List all hotspot locations for the logged-in vendor
    """
    vendor = request.user.vendor
    locations = vendor.locations.all().order_by('-created_at')

    return render(request, 'hotspot/locations.html', {
        'locations': locations,
        'vendor': vendor
    })


@login_required
def add_location(request):
    """
    Add a new hotspot location (PENDING approval)
    + Automatically attach default subscription (payment-controlled)
    """
    if request.method == 'POST':
        form = HotspotLocationForm(request.POST)
        if form.is_valid():
            try:
                location = form.save(commit=False)
                location.vendor = request.user.vendor
                location.save()

                # 🔑 CREATE DEFAULT SUBSCRIPTION (PAYMENT APP)
                create_default_location_subscription(location)

                messages.success(
                    request,
                    f'Location "{location.site_name}" submitted for approval. '
                    'Admin will review and activate it soon.'
                )

            except ValidationError as e:
                messages.error(request, e.message)
            except Exception:
                messages.error(
                    request,
                    "Location created, but subscription setup failed. "
                    "Please contact support."
                )

            return redirect('locations_list')

    # No GET rendering here (modal-based UI)
    return redirect('locations_list')


@login_required
def location_status(request, location_id):
    """
    AJAX endpoint to check location status
    (Vendor-only, internal use)
    """
    try:
        vendor = request.user.vendor
    except Exception:
        return JsonResponse(
            {'error': 'You are not registered as a vendor.'},
            status=403
        )

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

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Package
from hotspot.models import HotspotLocation

@login_required
def package_list(request):
    vendor = request.user.vendor

    # Only vendor's ACTIVE locations (for dropdown)
    locations = HotspotLocation.objects.filter(
        vendor=vendor,
        status='ACTIVE'
    )

    # List all vendor packages
    packages = Package.objects.filter(
        location__vendor=vendor
    ).select_related('location')

    if request.method == 'POST':
        # SECURITY: ensure location belongs to vendor
        location = HotspotLocation.objects.get(
            id=request.POST['location'],
            vendor=vendor,
            status='ACTIVE'
        )

        Package.objects.create(
            location=location,
            name=request.POST['name'],
            price=request.POST['price'],
            is_active=bool(request.POST.get('is_active'))
        )

        return redirect('package_list')

    return render(request, 'packages/package_list.html', {
        'packages': packages,
        'locations': locations
    })

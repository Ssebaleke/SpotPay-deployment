from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import Package
from hotspot.models import HotspotLocation


@login_required
def package_list(request):
    vendor = request.user.vendor
    locations = HotspotLocation.objects.filter(vendor=vendor, status='ACTIVE')
    packages = Package.objects.filter(location__vendor=vendor).select_related('location').order_by('-created_at')

    if request.method == 'POST':
        action = request.POST.get('action')

        # CREATE
        if action == 'create':
            location = get_object_or_404(
                HotspotLocation,
                id=request.POST.get('location'),
                vendor=vendor,
                status='ACTIVE'
            )
            schedule_type = request.POST.get('schedule_type', 'ALWAYS')
            Package.objects.create(
                location=location,
                name=request.POST.get('name'),
                price=request.POST.get('price'),
                is_active=bool(request.POST.get('is_active')),
                schedule_type=schedule_type,
                scheduled_days=','.join(request.POST.getlist('scheduled_days')) if schedule_type == 'WEEKDAYS' else '',
                scheduled_date=request.POST.get('scheduled_date') or None,
                scheduled_start=request.POST.get('scheduled_start') or None,
                scheduled_end=request.POST.get('scheduled_end') or None,
            )

        # EDIT
        elif action == 'edit':
            package = get_object_or_404(
                Package,
                id=request.POST.get('package_id'),
                location__vendor=vendor
            )
            schedule_type = request.POST.get('schedule_type', 'ALWAYS')
            package.name = request.POST.get('name')
            package.price = request.POST.get('price')
            package.is_active = bool(request.POST.get('is_active'))
            package.schedule_type = schedule_type
            package.scheduled_days = ','.join(request.POST.getlist('scheduled_days')) if schedule_type == 'WEEKDAYS' else ''
            package.scheduled_date = request.POST.get('scheduled_date') or None
            package.scheduled_start = request.POST.get('scheduled_start') or None
            package.scheduled_end = request.POST.get('scheduled_end') or None

            location_id = request.POST.get('location')
            if location_id:
                location = get_object_or_404(
                    HotspotLocation,
                    id=location_id,
                    vendor=vendor,
                    status='ACTIVE'
                )
                package.location = location
            package.save()

        # 🔥 HARD DELETE (THIS IS THE CHANGE)
        elif action == 'delete':
            package = get_object_or_404(
                Package,
                id=request.POST.get('package_id'),
                location__vendor=vendor
            )

            package.delete()   # ❗ COMPLETELY REMOVED

        return redirect('package_list')

    return render(
        request,
        'packages/package_list.html',
        {
            'packages': packages,
            'locations': locations,
            'package_day_choices': Package.DAY_CHOICES,
        }
    )

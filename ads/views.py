from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse

from .models import Ad
from hotspot.models import HotspotLocation


@login_required
def ads_list(request):
    vendor = request.user.vendor

    locations = HotspotLocation.objects.filter(vendor=vendor)
    ads = Ad.objects.filter(location__vendor=vendor).select_related('location')

    if request.method == 'POST':
        location_id = request.POST.get('location')
        ad_type = request.POST.get('ad_type')
        file = request.FILES.get('file')

        if not location_id or not ad_type or not file:
            messages.error(request, "All fields are required.")
            return redirect('ads_list')

        location = get_object_or_404(
            HotspotLocation,
            id=location_id,
            vendor=vendor
        )

        Ad.objects.create(
            location=location,
            ad_type=ad_type,
            file=file
        )

        messages.success(request, "Ad uploaded successfully.")
        return redirect('ads_list')

    return render(request, 'ads/ads_list.html', {
        'ads': ads,
        'locations': locations
    })


@login_required
def delete_ad(request, id):
    ad = get_object_or_404(
        Ad,
        id=id,
        location__vendor=request.user.vendor
    )

    ad.delete()
    messages.success(request, "Ad deleted.")
    return redirect('ads_list')


# 🔥 Captive portal endpoint (NO LOGIN)
def portal_ads(request, location_id):
    ads = Ad.objects.filter(
        location_id=location_id,
        is_active=True
    )

    data = []
    for ad in ads:
        data.append({
            'type': ad.ad_type,
            'file': ad.file.url
        })

    return JsonResponse(data, safe=False)

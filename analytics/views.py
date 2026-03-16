from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages

from accounts.models import Vendor
from hotspot.models import HotspotLocation
from payments.models import Payment


@login_required
def analytics_dashboard(request):
    try:
        vendor = request.user.vendor
        if vendor.status != 'ACTIVE':
            messages.error(request, 'Your account is not approved.')
            return redirect('vendor_login')
    except Vendor.DoesNotExist:
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendor_login')

    locations = HotspotLocation.objects.filter(vendor=vendor, status='ACTIVE')

    # Per-location performance summary
    now = timezone.now()
    location_stats = []
    for loc in locations:
        qs = Payment.objects.filter(vendor=vendor, location=loc, purpose='TRANSACTION', status='SUCCESS')
        total = qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        count = qs.count()
        today_total = qs.filter(completed_at__date=now.date()).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        month_total = qs.filter(completed_at__year=now.year, completed_at__month=now.month).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        location_stats.append({
            'location': loc,
            'total': total,
            'count': count,
            'today': today_total,
            'month': month_total,
        })

    return render(request, 'analytics/dashboard.html', {
        'vendor': vendor,
        'active_page': 'analytics',
        'locations': locations,
        'location_stats': location_stats,
    })


@login_required
def analytics_data(request):
    try:
        vendor = request.user.vendor
        if vendor.status != 'ACTIVE':
            return JsonResponse({'error': 'Unauthorized'}, status=403)
    except Vendor.DoesNotExist:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    period = request.GET.get('period', 'weekly')
    location_id = request.GET.get('location', '')
    now = timezone.now()
    today = now.date()

    base_qs = Payment.objects.filter(
        vendor=vendor,
        purpose='TRANSACTION',
        status='SUCCESS',
    )

    if location_id:
        base_qs = base_qs.filter(location_id=location_id)

    if period == 'daily':
        # Last 24 hours by hour
        labels, values = [], []
        for h in range(23, -1, -1):
            hour_start = now - timedelta(hours=h + 1)
            hour_end = now - timedelta(hours=h)
            total = (
                base_qs.filter(completed_at__gte=hour_start, completed_at__lt=hour_end)
                .aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
            )
            labels.append(hour_start.strftime('%H:%M'))
            values.append(float(total))

    elif period == 'weekly':
        # Last 7 days
        labels, values = [], []
        for d in range(6, -1, -1):
            day = today - timedelta(days=d)
            total = (
                base_qs.filter(completed_at__date=day)
                .aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
            )
            labels.append(day.strftime('%a %d'))
            values.append(float(total))

    elif period == 'monthly':
        # Last 30 days
        labels, values = [], []
        for d in range(29, -1, -1):
            day = today - timedelta(days=d)
            total = (
                base_qs.filter(completed_at__date=day)
                .aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
            )
            labels.append(day.strftime('%b %d'))
            values.append(float(total))

    elif period == 'annual':
        # Last 12 months
        labels, values = [], []
        for m in range(11, -1, -1):
            month_date = (now.replace(day=1) - timedelta(days=m * 30)).replace(day=1)
            total = (
                base_qs.filter(
                    completed_at__year=month_date.year,
                    completed_at__month=month_date.month,
                ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
            )
            labels.append(month_date.strftime('%b %Y'))
            values.append(float(total))

    else:
        return JsonResponse({'error': 'Invalid period'}, status=400)

    # Summary totals
    total_all = base_qs.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    total_month = (
        base_qs.filter(completed_at__year=now.year, completed_at__month=now.month)
        .aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    )
    total_today = (
        base_qs.filter(completed_at__date=today)
        .aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    )

    return JsonResponse({
        'labels': labels,
        'values': values,
        'summary': {
            'total_all': float(total_all),
            'total_month': float(total_month),
            'total_today': float(total_today),
        }
    })

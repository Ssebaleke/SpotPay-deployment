from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
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

    now = timezone.now()
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    locations = HotspotLocation.objects.filter(vendor=vendor)
    base_qs = Payment.objects.filter(vendor=vendor, purpose='TRANSACTION', status='SUCCESS')

    total_revenue   = base_qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')
    total_customers = base_qs.count()
    today_revenue   = base_qs.filter(completed_at__date=today).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    today_customers = base_qs.filter(completed_at__date=today).count()
    week_revenue    = base_qs.filter(completed_at__date__gte=week_start).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    week_customers  = base_qs.filter(completed_at__date__gte=week_start).count()
    month_revenue   = base_qs.filter(completed_at__year=now.year, completed_at__month=now.month).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    month_customers = base_qs.filter(completed_at__year=now.year, completed_at__month=now.month).count()

    location_rows = []
    for loc in locations:
        qs = base_qs.filter(location=loc)
        location_rows.append({
            'id': loc.id,
            'name': loc.site_name,
            'revenue': qs.aggregate(t=Sum('amount'))['t'] or Decimal('0'),
            'customers': qs.count(),
        })

    top_packages = (
        base_qs.values('package__name')
        .annotate(sales=Count('id'), revenue=Sum('amount'))
        .order_by('-sales')[:6]
    )

    return render(request, 'analytics/dashboard.html', {
        'vendor': vendor,
        'locations': locations,
        'location_rows': location_rows,
        'total_revenue': total_revenue,
        'total_customers': total_customers,
        'today_revenue': today_revenue,
        'today_customers': today_customers,
        'week_revenue': week_revenue,
        'week_customers': week_customers,
        'month_revenue': month_revenue,
        'month_customers': month_customers,
        'top_packages': list(top_packages),
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
    today = timezone.localdate()

    base_qs = Payment.objects.filter(
        vendor=vendor,
        purpose='TRANSACTION',
        status='SUCCESS',
    )

    if location_id:
        base_qs = base_qs.filter(location_id=location_id)

    if period == 'daily':
        labels, revenue, customers = [], [], []
        for h in range(23, -1, -1):
            hour_start = now - timedelta(hours=h + 1)
            hour_end   = now - timedelta(hours=h)
            qs = base_qs.filter(completed_at__gte=hour_start, completed_at__lt=hour_end)
            labels.append(hour_start.strftime('%H:%M'))
            revenue.append(float(qs.aggregate(t=Sum('amount'))['t'] or 0))
            customers.append(qs.count())

    elif period == 'weekly':
        labels, revenue, customers = [], [], []
        for d in range(6, -1, -1):
            day = today - timedelta(days=d)
            qs = base_qs.filter(completed_at__date=day)
            labels.append(day.strftime('%a %d'))
            revenue.append(float(qs.aggregate(t=Sum('amount'))['t'] or 0))
            customers.append(qs.count())

    elif period == 'monthly':
        labels, revenue, customers = [], [], []
        for d in range(29, -1, -1):
            day = today - timedelta(days=d)
            qs = base_qs.filter(completed_at__date=day)
            labels.append(day.strftime('%b %d'))
            revenue.append(float(qs.aggregate(t=Sum('amount'))['t'] or 0))
            customers.append(qs.count())

    elif period == 'annual':
        labels, revenue, customers = [], [], []
        for m in range(11, -1, -1):
            month_date = (now.replace(day=1) - timedelta(days=m * 30)).replace(day=1)
            qs = base_qs.filter(completed_at__year=month_date.year, completed_at__month=month_date.month)
            labels.append(month_date.strftime('%b %Y'))
            revenue.append(float(qs.aggregate(t=Sum('amount'))['t'] or 0))
            customers.append(qs.count())

    else:
        return JsonResponse({'error': 'Invalid period'}, status=400)

    week_start  = today - timedelta(days=today.weekday())
    total_all   = base_qs.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    total_month = base_qs.filter(completed_at__year=now.year, completed_at__month=now.month).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    total_today = base_qs.filter(completed_at__date=today).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    total_week  = base_qs.filter(completed_at__date__gte=week_start).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    count_all   = base_qs.count()
    count_month = base_qs.filter(completed_at__year=now.year, completed_at__month=now.month).count()
    count_today = base_qs.filter(completed_at__date=today).count()
    count_week  = base_qs.filter(completed_at__date__gte=week_start).count()

    top_pkgs = list(
        base_qs.values('package__name')
        .annotate(sales=Count('id'), revenue=Sum('amount'))
        .order_by('-sales')[:6]
    )

    return JsonResponse({
        'labels': labels,
        'revenue': revenue,
        'customers': customers,
        'summary': {
            'total_revenue': float(total_all),
            'month_revenue': float(total_month),
            'today_revenue': float(total_today),
            'week_revenue': float(total_week),
            'total_customers': count_all,
            'month_customers': count_month,
            'today_customers': count_today,
            'week_customers': count_week,
        },
        'top_packages': [
            {'name': p['package__name'] or 'Unknown', 'sales': p['sales'], 'revenue': float(p['revenue'] or 0)}
            for p in top_pkgs
        ],
    })

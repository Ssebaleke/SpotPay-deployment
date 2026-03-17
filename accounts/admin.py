# accounts/admin.py
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.html import format_html
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from decimal import Decimal
from datetime import timedelta

from .models import Vendor
from sms.services.notifications import notify_vendor_approval


class SpotPayAdminSite(AdminSite):
    site_header = "SpotPay Administration"
    site_title = "SpotPay Admin"
    index_title = "System Overview"
    index_template = "admin/index.html"

    def index(self, request, extra_context=None):
        from payments.models import Payment, PaymentSplit
        from hotspot.models import HotspotLocation
        from wallets.models import VendorWallet, WithdrawalRequest

        now = timezone.now()
        today = now.date()
        month_start = now - timedelta(days=30)

        # ── existing txn stats ──
        txn_qs = Payment.objects.filter(purpose="TRANSACTION", initiated_at__gte=month_start)
        success_qs = txn_qs.filter(status="SUCCESS")
        failed_count = txn_qs.filter(status="FAILED").count()
        pending_count = txn_qs.filter(status="PENDING").count()
        total_count = txn_qs.count()
        success_count = success_qs.count()

        trend_labels, trend_values = [], []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            total = Payment.objects.filter(
                purpose="TRANSACTION", status="SUCCESS", completed_at__date=day
            ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
            trend_labels.append(day.strftime("%a %d"))
            trend_values.append(float(total))

        monthly_labels, monthly_revenue, monthly_payers = [], [], []
        for offset in range(11, -1, -1):
            month_date = (now - timedelta(days=offset * 30)).replace(day=1)
            month_end = (month_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            rev = Payment.objects.filter(
                purpose="TRANSACTION", status="SUCCESS",
                completed_at__gte=month_date, completed_at__lt=month_end
            ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
            payers = Payment.objects.filter(
                purpose="TRANSACTION", status="SUCCESS",
                completed_at__gte=month_date, completed_at__lt=month_end
            ).values("phone").distinct().count()
            monthly_labels.append(month_date.strftime("%b %Y"))
            monthly_revenue.append(float(rev))
            monthly_payers.append(payers)

        vendor_active = Vendor.objects.filter(status="ACTIVE").count()
        vendor_pending = Vendor.objects.filter(status="PENDING").count()
        vendor_suspended = Vendor.objects.filter(status="SUSPENDED").count()
        vendor_rejected = Vendor.objects.filter(status="REJECTED").count()

        from sms.models import SMSPurchase, SMSProvider
        import requests as http_requests
        from django.core.cache import cache

        ugsms_balance_units = cache.get("ugsms_balance")
        if ugsms_balance_units is None:
            ugsms_balance_units = "N/A"
            sms_provider = SMSProvider.objects.filter(is_active=True).first()
            if sms_provider:
                try:
                    resp = http_requests.get(
                        "https://ugsms.com/api/v2/account/balance",
                        headers={"X-API-Key": sms_provider.api_key},
                        timeout=5
                    )
                    if resp.status_code == 200:
                        rdata = resp.json()
                        ugsms_balance_units = rdata.get("balance") or rdata.get("data", {}).get("balance", "N/A")
                        cache.set("ugsms_balance", ugsms_balance_units, 300)
                except Exception:
                    pass

        total_sms_revenue = SMSPurchase.objects.filter(status="SUCCESS").aggregate(t=Sum("amount_paid"))["t"] or 0
        pending_wd_qs = WithdrawalRequest.objects.filter(status=WithdrawalRequest.STATUS_PENDING)

        # ── SpotPay Commission Earnings ──
        def commission_sum(qs):
            return qs.aggregate(t=Sum("spotpay_amount"))["t"] or Decimal("0")

        split_qs = PaymentSplit.objects.filter(payment__status="SUCCESS")
        earn_today    = commission_sum(split_qs.filter(created_at__date=today))
        earn_week     = commission_sum(split_qs.filter(created_at__gte=now - timedelta(days=7)))
        earn_month    = commission_sum(split_qs.filter(created_at__gte=now - timedelta(days=30)))
        earn_year     = commission_sum(split_qs.filter(created_at__gte=now - timedelta(days=365)))
        earn_alltime  = commission_sum(split_qs)

        # ── Subscription revenue (SUBSCRIPTION payments) ──
        sub_qs = Payment.objects.filter(purpose="SUBSCRIPTION", status="SUCCESS")
        sub_today   = sub_qs.filter(completed_at__date=today).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        sub_week    = sub_qs.filter(completed_at__gte=now - timedelta(days=7)).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        sub_month   = sub_qs.filter(completed_at__gte=now - timedelta(days=30)).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        sub_year    = sub_qs.filter(completed_at__gte=now - timedelta(days=365)).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        sub_alltime = sub_qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")

        # ── Commission chart (last 12 months) ──
        commission_chart_labels, commission_chart_values = [], []
        for offset in range(11, -1, -1):
            month_date = (now - timedelta(days=offset * 30)).replace(day=1)
            month_end = (month_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            val = commission_sum(split_qs.filter(created_at__gte=month_date, created_at__lt=month_end))
            commission_chart_labels.append(month_date.strftime("%b %Y"))
            commission_chart_values.append(float(val))

        extra_context = extra_context or {}
        extra_context.update({
            "sp_total_sales": Payment.objects.filter(purpose="TRANSACTION", status="SUCCESS").aggregate(t=Sum("amount"))["t"] or Decimal("0"),
            "sp_total_vendors": Vendor.objects.count(),
            "sp_active_vendors": Vendor.objects.filter(status="ACTIVE").count(),
            "sp_pending_vendors": Vendor.objects.filter(status="PENDING").count(),
            "sp_total_locations": HotspotLocation.objects.count(),
            "sp_active_locations": HotspotLocation.objects.filter(status="ACTIVE").count(),
            "sp_ugsms_balance": ugsms_balance_units,
            "sp_total_sms_revenue": total_sms_revenue,
            "sp_total_txn": total_count,
            "sp_success_txn": success_count,
            "sp_failed_txn": failed_count,
            "sp_pending_txn": pending_count,
            "sp_success_rate": round((success_count / total_count) * 100) if total_count > 0 else 0,
            "sp_wallet_pool": VendorWallet.objects.aggregate(t=Sum("balance"))["t"] or Decimal("0"),
            "sp_pending_withdrawals": pending_wd_qs.count(),
            "sp_withdrawals_total": pending_wd_qs.aggregate(t=Sum("amount"))["t"] or Decimal("0"),
            "sp_trend_labels": trend_labels,
            "sp_trend_values": trend_values,
            "sp_monthly_labels": monthly_labels,
            "sp_monthly_revenue": monthly_revenue,
            "sp_monthly_payers": monthly_payers,
            "sp_vendor_active": vendor_active,
            "sp_vendor_pending": vendor_pending,
            "sp_vendor_suspended": vendor_suspended,
            "sp_vendor_rejected": vendor_rejected,
            # commission
            "sp_earn_today": earn_today,
            "sp_earn_week": earn_week,
            "sp_earn_month": earn_month,
            "sp_earn_year": earn_year,
            "sp_earn_alltime": earn_alltime,
            # subscriptions
            "sp_sub_today": sub_today,
            "sp_sub_week": sub_week,
            "sp_sub_month": sub_month,
            "sp_sub_year": sub_year,
            "sp_sub_alltime": sub_alltime,
            # commission chart
            "sp_commission_chart_labels": commission_chart_labels,
            "sp_commission_chart_values": commission_chart_values,
        })
        return super().index(request, extra_context)


admin_site = SpotPayAdminSite(name="spotpay_admin")


class VendorAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'contact_person', 'business_phone', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('company_name', 'contact_person', 'business_phone', 'business_email')
    readonly_fields = ('created_at', 'updated_at', 'approved_at')
    
    fieldsets = (
        ('Company Information', {
            'fields': ('user', 'company_name', 'business_address')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'business_phone', 'business_email')
        }),
        ('Status', {
            'fields': ('status', 'approved_by', 'approved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_vendors', 'reject_vendors', 'suspend_vendors']
    
    def approve_vendors(self, request, queryset):
        updated = 0
        for vendor in queryset.select_related('user'):
            vendor.status = 'ACTIVE'
            vendor.approved_by = request.user
            vendor.approved_at = timezone.now()
            vendor.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
            vendor.user.is_active = True
            vendor.user.save()
            notify_vendor_approval(vendor)
            updated += 1
        self.message_user(request, f'{updated} vendor(s) approved and activated.')
    approve_vendors.short_description = "Approve selected vendors"
    
    def reject_vendors(self, request, queryset):
        updated = queryset.update(status='REJECTED')
        # Deactivate the user account
        for vendor in queryset:
            vendor.user.is_active = False
            vendor.user.save()
        self.message_user(request, f'{updated} vendor(s) rejected and deactivated.')
    reject_vendors.short_description = "Reject selected vendors"
    
    def suspend_vendors(self, request, queryset):
        updated = queryset.update(status='SUSPENDED')
        # Deactivate the user account
        for vendor in queryset:
            vendor.user.is_active = False
            vendor.user.save()
        self.message_user(request, f'{updated} vendor(s) suspended and deactivated.')
    suspend_vendors.short_description = "Suspend selected vendors"


admin_site.register(Vendor, VendorAdmin)

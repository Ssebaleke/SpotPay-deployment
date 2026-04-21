from django.contrib import admin
from django.utils import timezone
from django.db.models import Sum
from django.utils.html import format_html
from .models import (
    VendorWallet,
    WalletTransaction,
    WithdrawalRequest,
    WalletOTP,
    WalletPasswordToken,
    SpotPayEarning,
)
from sms.services.notifications import notify_withdrawal_receipt


# =====================================================
# VENDOR WALLET
# =====================================================

@admin.register(VendorWallet)
class VendorWalletAdmin(admin.ModelAdmin):
    list_display = (
        'vendor',
        'balance',
        'is_locked',
        'created_at',
    )
    search_fields = ('vendor__company_name',)
    readonly_fields = ('created_at', 'updated_at')


# =====================================================
# WALLET TRANSACTIONS (LEDGER)
# =====================================================

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'get_vendor',
        'transaction_type',
        'reason',
        'amount',
        'reference',
        'created_at',
    )
    list_filter = ('transaction_type', 'reason', 'created_at')
    search_fields = (
        'wallet__vendor__company_name',
        'reference',
    )
    readonly_fields = ('created_at',)

    def get_vendor(self, obj):
        return obj.wallet.vendor

    get_vendor.short_description = 'Vendor'


# =====================================================
# WITHDRAWAL REQUESTS
# =====================================================

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = (
        'get_vendor',
        'requested_amount',
        'get_gateway_fee',
        'get_spotpay_fee',
        'amount',
        'payout_method',
        'payout_phone',
        'payout_name',
        'status',
        'reference',
        'created_at',
    )
    list_filter = ('status', 'payout_method', 'created_at')
    search_fields = (
        'wallet__vendor__company_name',
        'reference',
        'payout_phone',
        'payout_name',
    )
    readonly_fields = ('created_at', 'updated_at', 'reference', 'requested_amount', 'get_gateway_fee', 'get_spotpay_fee')
    ordering = ('-created_at',)
    actions = ['mark_as_paid']

    fieldsets = (
        ('Vendor & Amount', {
            'fields': ('wallet', 'requested_amount', 'get_gateway_fee', 'get_spotpay_fee', 'amount', 'status', 'reference')
        }),
        ('Payout Details', {
            'fields': ('payout_method', 'payout_phone', 'payout_name'),
            'description': 'Where to send the money'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def get_vendor(self, obj):
        return obj.wallet.vendor if obj.wallet else '—'
    get_vendor.short_description = 'Vendor'

    def _get_config(self):
        from payments.models import PaymentSystemConfig
        return PaymentSystemConfig.get()

    def requested_amount(self, obj):
        config = self._get_config()
        total = obj.amount + config.withdrawal_gateway_fee + config.withdrawal_spotpay_fee
        return f'UGX {total:,.0f}'
    requested_amount.short_description = 'Requested Amount'

    def get_gateway_fee(self, obj):
        config = self._get_config()
        return f'UGX {config.withdrawal_gateway_fee:,.0f}'
    get_gateway_fee.short_description = 'Gateway Fee'

    def get_spotpay_fee(self, obj):
        config = self._get_config()
        return f'UGX {config.withdrawal_spotpay_fee:,.0f}'
    get_spotpay_fee.short_description = 'SpotPay Fee'

    def mark_as_paid(self, request, queryset):
        count = 0
        for withdrawal in queryset.exclude(status=WithdrawalRequest.STATUS_PAID):
            withdrawal.status = WithdrawalRequest.STATUS_PAID
            withdrawal.updated_at = timezone.now()
            withdrawal.save(update_fields=['status', 'updated_at'])
            try:
                notify_withdrawal_receipt(withdrawal)
            except Exception:
                pass
            count += 1
        self.message_user(request, f'{count} withdrawal(s) marked as paid and receipt sent to vendor(s).')
    mark_as_paid.short_description = 'Mark selected as Paid & send receipt to vendor'


# =====================================================
# WALLET OTP
# =====================================================

@admin.register(WalletOTP)
class WalletOTPAdmin(admin.ModelAdmin):
    list_display = (
        'vendor',
        'code',
        'is_used',
        'expires_at',
        'created_at',
    )
    readonly_fields = ('created_at',)


# =====================================================
# WALLET PASSWORD TOKENS
# =====================================================

@admin.register(WalletPasswordToken)
class WalletPasswordTokenAdmin(admin.ModelAdmin):
    list_display = (
        'wallet',
        'token',
        'expires_at',
        'created_at',
    )
    readonly_fields = ('created_at',)


# =====================================================
# SPOTPAY EARNINGS (COMMISSION TRACKER)
# =====================================================

@admin.register(SpotPayEarning)
class SpotPayEarningAdmin(admin.ModelAdmin):
    list_display = (
        'source_badge',
        'amount_display',
        'reference',
        'created_at',
    )
    list_filter = ('source', 'created_at')
    search_fields = ('reference',)
    readonly_fields = ('source', 'amount', 'reference', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def source_badge(self, obj):
        colors = {
            'COMMISSION': '#16a34a',
            'SUBSCRIPTION': '#2563eb',
            'SMS_PURCHASE': '#9333ea',
            'WITHDRAWAL_FEE': '#d97706',
        }
        color = colors.get(obj.source, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_source_display()
        )
    source_badge.short_description = 'Source'

    def amount_display(self, obj):
        return format_html('<strong>UGX {:,.0f}</strong>', obj.amount)
    amount_display.short_description = 'Amount'

    def changelist_view(self, request, extra_context=None):
        qs = self.get_queryset(request)
        totals = qs.values('source').annotate(total=Sum('amount'))
        total_map = {row['source']: row['total'] for row in totals}
        grand_total = qs.aggregate(total=Sum('amount'))['total'] or 0

        summary_rows = ''.join(
            f'<tr><td style="padding:4px 12px;">{label}</td>'
            f'<td style="padding:4px 12px;font-weight:600;">UGX {total_map.get(key, 0):,.0f}</td></tr>'
            for key, label in SpotPayEarning.SOURCES
        )

        summary_html = (
            f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin-bottom:16px;">'
            f'<strong style="font-size:14px;">💰 SpotPay Commission Summary</strong>'
            f'<table style="margin-top:8px;width:100%;max-width:400px;">'
            f'{summary_rows}'
            f'<tr style="border-top:2px solid #16a34a;">'
            f'<td style="padding:6px 12px;font-weight:700;">Total Earned</td>'
            f'<td style="padding:6px 12px;font-weight:700;color:#16a34a;">UGX {grand_total:,.0f}</td>'
            f'</tr></table></div>'
        )

        extra_context = extra_context or {}
        extra_context['summary_html'] = summary_html
        return super().changelist_view(request, extra_context=extra_context)

    class Media:
        css = {}

    # Inject summary into the page
    change_list_template = 'admin/wallets/spotpayearning/change_list.html'

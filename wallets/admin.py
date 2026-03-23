from django.contrib import admin
from django.utils import timezone
from .models import (
    VendorWallet,
    WalletTransaction,
    WithdrawalRequest,
    WalletOTP,
    WalletPasswordToken,
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
    readonly_fields = ('created_at', 'updated_at', 'reference')
    ordering = ('-created_at',)
    actions = ['mark_as_paid']

    fieldsets = (
        ('Vendor & Amount', {
            'fields': ('wallet', 'amount', 'status', 'reference')
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

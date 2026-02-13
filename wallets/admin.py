from django.contrib import admin
from .models import (
    VendorWallet,
    WalletTransaction,
    WithdrawalRequest,
    WalletOTP,
    WalletPasswordToken,
)


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
        'status',
        'reference',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'wallet__vendor__company_name',
        'reference',
    )
    readonly_fields = ('created_at', 'updated_at')

    def get_vendor(self, obj):
        return obj.wallet.vendor

    get_vendor.short_description = 'Vendor'


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

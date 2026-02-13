from django.contrib import admin
from django.utils.html import format_html

from .models import (
    SMSProvider,
    SMSPricing,
    VendorSMSWallet,
    SMSPurchase,
    SMSLog,
)


# =====================================================
# 1. SMS PROVIDERS (ADMIN CONTROLS ACTIVE PROVIDER)
# =====================================================

@admin.register(SMSProvider)
class SMSProviderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider_type",
        "active_status",
        "created_at",
    )
    list_filter = ("provider_type", "is_active")
    search_fields = ("name",)
    readonly_fields = ("created_at",)

    def active_status(self, obj):
        if obj.is_active:
            return format_html('<b style="color: green;">ACTIVE</b>')
        return format_html('<b style="color: red;">INACTIVE</b>')

    active_status.short_description = "Status"

    def save_model(self, request, obj, form, change):
        """
        Ensure ONLY ONE SMS provider is active at a time
        """
        if obj.is_active:
            SMSProvider.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


# =====================================================
# 2. SMS PRICING (ADMIN SETS PRICE PER SMS)
# =====================================================

@admin.register(SMSPricing)
class SMSPricingAdmin(admin.ModelAdmin):
    list_display = (
        "price_per_sms",
        "currency",
        "active_status",
        "updated_at",
    )
    list_filter = ("is_active",)
    readonly_fields = ("updated_at",)

    def active_status(self, obj):
        if obj.is_active:
            return format_html('<b style="color: green;">ACTIVE</b>')
        return format_html('<b style="color: red;">INACTIVE</b>')

    active_status.short_description = "Status"

    def save_model(self, request, obj, form, change):
        """
        Ensure ONLY ONE pricing is active at a time
        """
        if obj.is_active:
            SMSPricing.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


# =====================================================
# 3. VENDOR SMS WALLET (READ-ONLY FINANCIAL VIEW)
# =====================================================

@admin.register(VendorSMSWallet)
class VendorSMSWalletAdmin(admin.ModelAdmin):
    list_display = (
        "vendor",
        "balance_units",
        "balance_amount",
        "updated_at",
    )
    search_fields = (
        "vendor__company_name",
        "vendor__user__username",
    )
    readonly_fields = (
        "vendor",
        "balance_units",
        "balance_amount",
        "updated_at",
    )

    def has_add_permission(self, request):
        # Wallets are auto-created by system
        return False

    def has_delete_permission(self, request, obj=None):
        # Prevent accidental deletion
        return False


# =====================================================
# 4. SMS PURCHASES (AUDIT TRAIL)
# =====================================================

@admin.register(SMSPurchase)
class SMSPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "vendor",
        "amount_paid",
        "sms_units_credited",
        "price_per_sms",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "vendor__company_name",
        "vendor__user__username",
    )
    readonly_fields = (
        "vendor",
        "amount_paid",
        "sms_units_credited",
        "price_per_sms",
        "status",
        "created_at",
    )

    def has_add_permission(self, request):
        # Created by system after payment
        return False

    def has_delete_permission(self, request, obj=None):
        # Keep audit trail intact
        return False


# =====================================================
# 5. SMS LOGS (SYSTEM ACTIVITY)
# =====================================================

@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = (
        "vendor",
        "phone",
        "short_message",
        "provider",
        "status",
        "created_at",
    )
    list_filter = ("status", "provider", "created_at")
    search_fields = ("phone", "vendor__company_name")
    readonly_fields = (
        "vendor",
        "phone",
        "message",
        "provider",
        "status",
        "created_at",
    )

    def short_message(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message

    short_message.short_description = "Message Preview"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

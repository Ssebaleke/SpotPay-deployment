from django.contrib import admin
from django.utils.html import format_html

from .models import (
    SMSProvider,
    EmailProvider,
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


@admin.register(EmailProvider)
class EmailProviderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider_type",
        "from_email",
        "active_status",
        "created_at",
    )
    list_filter = ("provider_type", "is_active")
    search_fields = ("name", "from_email")
    readonly_fields = ("created_at",)

    def active_status(self, obj):
        if obj.is_active:
            return format_html('<b style="color: green;">ACTIVE</b>')
        return format_html('<b style="color: red;">INACTIVE</b>')

    active_status.short_description = "Status"

    def save_model(self, request, obj, form, change):
        if obj.is_active:
            EmailProvider.objects.exclude(pk=obj.pk).update(is_active=False)
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
        "created_at",
        "vendor",
        "phone",
        "voucher_code",
        "status_badge",
        "failure_reason",
        "provider",
        "payment_amount",
        "payment_package",
    )
    list_filter = ("status", "provider", "created_at", "vendor")
    search_fields = ("phone", "voucher_code", "vendor__company_name")
    readonly_fields = (
        "vendor",
        "phone",
        "voucher_code",
        "payment",
        "message",
        "provider",
        "status",
        "failure_reason",
        "created_at",
    )
    date_hierarchy = "created_at"

    def status_badge(self, obj):
        if obj.status == "SENT":
            return format_html('<b style="color:green">✓ Sent</b>')
        return format_html('<b style="color:red">✗ {}</b>', obj.status)
    status_badge.short_description = "Status"

    def payment_amount(self, obj):
        if obj.payment:
            return f"UGX {obj.payment.amount}"
        return "-"
    payment_amount.short_description = "Amount"

    def payment_package(self, obj):
        if obj.payment and obj.payment.package:
            return obj.payment.package.name
        return "-"
    payment_package.short_description = "Package"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    PaymentProvider,
    PaymentSystemConfig,
    Payment,
    PaymentSplit,
    PaymentVoucher,
)


@admin.register(PaymentProvider)
class PaymentProviderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider_type",
        "environment",
        "base_url",
        "is_active",
        "created_at",
    )
    list_filter = ("provider_type", "environment", "is_active")
    search_fields = ("name", "base_url", "api_key")
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Provider Info", {
            "fields": ("name", "provider_type", "environment", "is_active")
        }),
        ("API Settings", {
            "fields": ("base_url", "api_key", "api_secret")
        }),
        ("Meta", {
            "fields": ("created_at",)
        }),
    )


@admin.register(PaymentSystemConfig)
class PaymentSystemConfigAdmin(admin.ModelAdmin):
    list_display = ("base_system_percentage", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "purpose",
        "payer_type",
        "status",
        "amount",
        "currency",
        "phone",
        "vendor",
        "location",
        "package",
        "provider",
        "provider_reference",
        "external_reference",
        "issued_voucher_code",
        "initiated_at",
        "completed_at",
    )

    list_filter = (
        "status",
        "purpose",
        "payer_type",
        "currency",
        "provider",
        "initiated_at",
        "completed_at",
    )

    search_fields = (
        "uuid",
        "phone",
        "provider_reference",
        "external_reference",
        "vendor__user__username",   # adjust if your Vendor model differs
        "location__name",          # adjust if your HotspotLocation differs
        "package__name",           # adjust if your Package model differs
    )

    readonly_fields = (
        "uuid",
        "initiated_at",
        "completed_at",
        "provider_reference",
        "external_reference",
        "processor_message",
        "raw_callback_pretty",
    )

    fieldsets = (
        ("Payment", {
            "fields": (
                "uuid", "status", "purpose", "payer_type",
                "amount", "currency",
                "phone",
                "vendor", "location", "package",
            )
        }),
        ("Hotspot Info (optional)", {
            "fields": ("mac_address", "ip_address"),
        }),
        ("Provider", {
            "fields": (
                "provider",
                "provider_reference",
                "external_reference",
                "processor_message",
            )
        }),
        ("Timestamps", {
            "fields": ("initiated_at", "completed_at")
        }),
        ("Webhook Raw Data", {
            "fields": ("raw_callback_pretty",)
        }),
    )

    def issued_voucher_code(self, obj):
        """
        Shows voucher code if PaymentVoucher exists.
        """
        try:
            return obj.issued_voucher.voucher.code
        except Exception:
            return "-"
    issued_voucher_code.short_description = "Voucher"

    def raw_callback_pretty(self, obj):
        if not obj.raw_callback_data:
            return "-"
        # show raw json in readable format
        return format_html(
            "<pre style='white-space:pre-wrap;max-width:900px;'>{}</pre>",
            obj.raw_callback_data
        )
    raw_callback_pretty.short_description = "Raw Callback Data"


@admin.register(PaymentSplit)
class PaymentSplitAdmin(admin.ModelAdmin):
    list_display = (
        "payment",
        "base_system_percentage",
        "subscription_percentage",
        "admin_amount",
        "vendor_amount",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("payment__uuid",)
    readonly_fields = ("created_at",)


@admin.register(PaymentVoucher)
class PaymentVoucherAdmin(admin.ModelAdmin):
    list_display = ("payment", "voucher", "issued_at")
    list_filter = ("issued_at",)
    search_fields = (
        "payment__uuid",
        "voucher__code",  # assumes Voucher has code field
    )
    readonly_fields = ("issued_at",)

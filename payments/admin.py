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
        "webhook_url_display",
        "created_at",
    )
    list_filter = ("provider_type", "environment", "is_active")
    search_fields = ("name", "base_url", "api_key")
    readonly_fields = ("created_at", "webhook_url_display")

    fieldsets = (
        ("Provider Info", {
            "fields": ("name", "provider_type", "environment", "is_active")
        }),
        ("API Settings", {
            "fields": ("base_url", "api_key", "api_secret", "transaction_pin", "gateway_fee_percentage")
        }),
        ("Webhook URL (register this in MakyPay dashboard)", {
            "fields": ("webhook_url_display",)
        }),
        ("Meta", {
            "fields": ("created_at",)
        }),
    )

    def webhook_url_display(self, obj):
        from django.conf import settings
        url = f"{settings.SITE_URL}/payments/webhook/makypay/"
        return format_html(
            '<code style="background:#f1f5f9;padding:4px 8px;border-radius:4px;">{}</code>',
            url
        )
    webhook_url_display.short_description = "Webhook URL"


@admin.register(PaymentSystemConfig)
class PaymentSystemConfigAdmin(admin.ModelAdmin):
    list_display = ("subscription_mode_percentage", "percentage_mode_percentage", "updated_at")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("SpotPay Commission Rates", {
            "description": "Set how much SpotPay takes from each sale depending on the location's subscription mode.",
            "fields": ("subscription_mode_percentage", "percentage_mode_percentage"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def has_add_permission(self, request):
        return not PaymentSystemConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "purpose",
        "status_badge",
        "amount",
        "phone",
        "vendor",
        "location",
        "package",
        "issued_voucher_code",
        "sms_status",
        "initiated_at",
        "completed_at",
    )

    list_filter = (
        "status",
        "purpose",
        "provider",
        "initiated_at",
    )

    search_fields = (
        "uuid",
        "phone",
        "provider_reference",
        "vendor__company_name",
        "location__site_name",
        "package__name",
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
        ("Hotspot Info", {
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

    def status_badge(self, obj):
        colors = {"SUCCESS": "green", "PENDING": "orange", "FAILED": "red"}
        color = colors.get(obj.status, "gray")
        return format_html('<b style="color:{}">{}</b>', color, obj.status)
    status_badge.short_description = "Status"

    def issued_voucher_code(self, obj):
        try:
            return obj.issued_voucher.voucher.code
        except Exception:
            return "-"
    issued_voucher_code.short_description = "Voucher"

    def sms_status(self, obj):
        from sms.models import SMSLog
        log = SMSLog.objects.filter(payment=obj).first()
        if not log:
            return format_html('<span style="color:gray">-</span>')
        if log.status == "SENT":
            return format_html('<b style="color:green">✓ Sent</b>')
        return format_html('<b style="color:red">✗ {}</b>', log.failure_reason or "Failed")
    sms_status.short_description = "SMS"

    def raw_callback_pretty(self, obj):
        if not obj.raw_callback_data:
            return "-"
        return format_html(
            "<pre style='white-space:pre-wrap;max-width:900px;'>{}</pre>",
            obj.raw_callback_data
        )
    raw_callback_pretty.short_description = "Raw Callback Data"


@admin.register(PaymentSplit)
class PaymentSplitAdmin(admin.ModelAdmin):
    list_display = (
        "payment",
        "subscription_mode",
        "gateway_fee_percentage",
        "gateway_fee_amount",
        "spotpay_percentage",
        "spotpay_amount",
        "vendor_amount",
        "created_at",
    )
    list_filter = ("subscription_mode", "created_at")
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

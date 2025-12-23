from django.contrib import admin
from django.utils.html import format_html

from .models import (
    PaymentProvider,
    LocationBillingProfile,
    Payment,
)


# =====================================================
# PAYMENT PROVIDERS (API CONFIGURATION)
# =====================================================

@admin.register(PaymentProvider)
class PaymentProviderAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'provider_type',
        'active_status',
        'created_at',
    )
    list_filter = ('provider_type', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_at',)

    def active_status(self, obj):
        if obj.is_active:
            return format_html(
                '<b style="color: green;">ACTIVE</b>'
            )
        return format_html(
            '<b style="color: red;">INACTIVE</b>'
        )

    active_status.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        """
        Ensure only ONE provider is active at a time
        """
        if obj.is_active:
            PaymentProvider.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


# =====================================================
# LOCATION BILLING PROFILE (MONETIZATION CONTROL)
# =====================================================
# Auto-created via signal — admin can only EDIT

@admin.register(LocationBillingProfile)
class LocationBillingProfileAdmin(admin.ModelAdmin):
    list_display = (
        'location',
        'subscription_required',
        'subscription_fee',
        'transaction_percentage',
        'subscription_status',
        'is_active',
    )

    list_filter = (
        'subscription_required',
        'is_active',
    )

    search_fields = (
        'location__site_name',
        'location__vendor__company_name',
    )

    readonly_fields = (
        'location',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        ('Location', {
            'fields': ('location',)
        }),
        ('Subscription Settings', {
            'fields': (
                'subscription_required',
                'subscription_fee',
                'subscription_period_days',
                'subscription_expires_at',
            )
        }),
        ('Transaction Percentage', {
            'fields': (
                'transaction_percentage',
            )
        }),
        ('Control', {
            'fields': (
                'is_active',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )

    def subscription_status(self, obj):
        if not obj.subscription_required:
            return format_html(
                '<span style="color: blue;">NO SUBSCRIPTION</span>'
            )

        if obj.subscription_valid():
            return format_html(
                '<span style="color: green; font-weight: bold;">ACTIVE</span>'
            )

        return format_html(
            '<span style="color: red; font-weight: bold;">EXPIRED</span>'
        )

    subscription_status.short_description = 'Subscription'


# =====================================================
# PAYMENTS (READ-ONLY AUDIT LOG)
# =====================================================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'payment_type',
        'vendor',
        'location',
        'amount',
        'status_badge',
        'provider',
        'created_at',
    )

    list_filter = (
        'payment_type',
        'status',
        'provider',
        'created_at',
    )

    search_fields = (
        'reference',
        'phone_number',
        'vendor__company_name',
        'location__site_name',
    )

    readonly_fields = (
        'reference',
        'payment_type',
        'phone_number',
        'amount',
        'status',
        'vendor',
        'location',
        'provider',
        'created_at',
        'updated_at',
    )

    def status_badge(self, obj):
        if obj.status == 'success':
            return format_html(
                '<b style="color: green;">SUCCESS</b>'
            )
        if obj.status == 'failed':
            return format_html(
                '<b style="color: red;">FAILED</b>'
            )
        return format_html(
            '<b style="color: orange;">PENDING</b>'
        )

    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


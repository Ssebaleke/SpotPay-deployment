from django.contrib import admin
from .models import LocationBillingProfile, PaymentProvider, Payment


@admin.register(LocationBillingProfile)
class LocationBillingProfileAdmin(admin.ModelAdmin):

    list_display = (
        'location',
        'subscription_mode',
        'subscription_fee',
        'transaction_percentage',
        'subscription_expires_at',
        'is_active',
    )

    list_filter = (
        'subscription_mode',
        'is_active',
    )

    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Location', {
            'fields': ('location',)
        }),
        ('Subscription Mode (ADMIN SETS)', {
            'fields': ('subscription_mode',)
        }),
        ('Subscription Settings', {
            'fields': (
                'subscription_fee',
                'subscription_period_days',
                'subscription_expires_at',
            )
        }),
        ('Transaction Percentage (MODE C ONLY)', {
            'fields': ('transaction_percentage',)
        }),
        ('Control', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(PaymentProvider)
class PaymentProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'is_active')
    list_filter = ('provider_type', 'is_active')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'payment_type',
        'amount',
        'status',
        'vendor',
        'location',
        'created_at'
    )
    list_filter = ('payment_type', 'status')
    search_fields = ('reference', 'phone_number')

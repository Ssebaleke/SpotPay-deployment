from django.contrib import admin
from .models import (
    PaymentProvider,
    PaymentSystemConfig,
    Payment,
    PaymentSplit
)


@admin.register(PaymentProvider)
class PaymentProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'environment', 'is_active')
    list_filter = ('provider_type', 'environment', 'is_active')


@admin.register(PaymentSystemConfig)
class PaymentSystemConfigAdmin(admin.ModelAdmin):
    list_display = ('base_system_percentage',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'purpose', 'amount', 'status', 'initiated_at')
    list_filter = ('purpose', 'status')
    readonly_fields = ('uuid', 'initiated_at', 'completed_at')


@admin.register(PaymentSplit)
class PaymentSplitAdmin(admin.ModelAdmin):
    list_display = ('payment', 'admin_amount', 'vendor_amount')

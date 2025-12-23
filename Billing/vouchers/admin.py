from django.contrib import admin
from .models import Voucher

@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'get_vendor',
        'package',
        'status',
        'created_at',
        'used_at'
    )

    list_filter = (
        'status',
        'package',
        'package__location__vendor',
    )

    search_fields = ('code',)

    def get_vendor(self, obj):
        return obj.package.location.vendor

    get_vendor.short_description = 'Vendor'

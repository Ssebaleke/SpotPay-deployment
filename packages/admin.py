from django.contrib import admin
from .models import Package

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'get_vendor',
        'location',
        'price',
        'is_active',
        'created_at'
    )

    list_filter = (
        'is_active',
        'location',
        'location__vendor',
    )

    search_fields = (
        'name',
        'location__site_name',
        'location__vendor__company_name',
    )

    def get_vendor(self, obj):
        return obj.location.vendor

    get_vendor.short_description = 'Vendor'

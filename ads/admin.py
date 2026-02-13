from django.contrib import admin
from django.utils.html import format_html
from .models import Ad


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'ad_type',
        'location',
        'vendor_name',
        'is_active',
        'created_at',
        'preview',
    )

    list_filter = (
        'ad_type',
        'is_active',
        'location__vendor',
        'created_at',
    )

    search_fields = (
        'location__site_name',
        'location__vendor__company_name',
    )

    readonly_fields = ('created_at', 'preview')

    def vendor_name(self, obj):
        return obj.location.vendor.company_name

    vendor_name.short_description = "Vendor"

    def preview(self, obj):
        if obj.ad_type == 'IMAGE':
            return format_html(
                '<img src="{}" style="height:60px;" />',
                obj.file.url
            )
        return format_html(
            '<video src="{}" style="height:60px;" muted></video>',
            obj.file.url
        )

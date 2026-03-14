from django.contrib import admin
from .models import Voucher, VoucherBatch, VoucherBatchDeletionLog


@admin.register(VoucherBatch)
class VoucherBatchAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'package',
        'uploaded_by',
        'source_filename',
        'total_uploaded',
        'created_at',
    )
    list_filter = ('created_at', 'package__location__vendor')
    search_fields = ('source_filename', 'package__name', 'package__location__site_name')


@admin.register(VoucherBatchDeletionLog)
class VoucherBatchDeletionLogAdmin(admin.ModelAdmin):
    list_display = (
        'batch_reference',
        'vendor',
        'deleted_by',
        'vouchers_deleted_count',
        'deleted_at',
    )
    list_filter = ('deleted_at', 'vendor')
    search_fields = ('batch_reference', 'source_filename', 'vendor__company_name')
    readonly_fields = (
        'batch_reference',
        'package',
        'vendor',
        'deleted_by',
        'source_filename',
        'vouchers_deleted_count',
        'deleted_at',
    )

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

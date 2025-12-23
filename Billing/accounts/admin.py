# accounts/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.utils import timezone
from .models import Vendor

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'contact_person', 'business_phone', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('company_name', 'contact_person', 'business_phone', 'business_email')
    readonly_fields = ('created_at', 'updated_at', 'approved_at')
    
    fieldsets = (
        ('Company Information', {
            'fields': ('user', 'company_name', 'business_address')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'business_phone', 'business_email')
        }),
        ('Status', {
            'fields': ('status', 'approved_by', 'approved_at')
        }),
        ('Financial', {
            'fields': ('sms_balance', 'wallet_balance')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_vendors', 'reject_vendors', 'suspend_vendors']
    
    def approve_vendors(self, request, queryset):
        updated = queryset.update(status='ACTIVE', approved_by=request.user, approved_at=timezone.now())
        # Also activate the user account
        for vendor in queryset:
            vendor.user.is_active = True
            vendor.user.save()
        self.message_user(request, f'{updated} vendor(s) approved and activated.')
    approve_vendors.short_description = "Approve selected vendors"
    
    def reject_vendors(self, request, queryset):
        updated = queryset.update(status='REJECTED')
        # Deactivate the user account
        for vendor in queryset:
            vendor.user.is_active = False
            vendor.user.save()
        self.message_user(request, f'{updated} vendor(s) rejected and deactivated.')
    reject_vendors.short_description = "Reject selected vendors"
    
    def suspend_vendors(self, request, queryset):
        updated = queryset.update(status='SUSPENDED')
        # Deactivate the user account
        for vendor in queryset:
            vendor.user.is_active = False
            vendor.user.save()
        self.message_user(request, f'{updated} vendor(s) suspended and deactivated.')
    suspend_vendors.short_description = "Suspend selected vendors"
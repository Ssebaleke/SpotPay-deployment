from django.contrib import admin, messages
from django.utils.html import format_html
from django.shortcuts import render, redirect
from django import forms
from django.urls import path
from django.db import transaction

from .models import (
    SMSProvider,
    EmailProvider,
    SMSPricing,
    VendorSMSWallet,
    SMSPurchase,
    SMSLog,
)


# =====================================================
# 1. SMS PROVIDERS (ADMIN CONTROLS ACTIVE PROVIDER)
# =====================================================

@admin.register(SMSProvider)
class SMSProviderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider_type",
        "active_status",
        "created_at",
    )
    list_filter = ("provider_type", "is_active")
    search_fields = ("name",)
    readonly_fields = ("created_at",)

    def active_status(self, obj):
        if obj.is_active:
            return format_html('<b style="color: green;">ACTIVE</b>')
        return format_html('<b style="color: red;">INACTIVE</b>')

    active_status.short_description = "Status"

    def save_model(self, request, obj, form, change):
        """
        Ensure ONLY ONE SMS provider is active at a time
        """
        if obj.is_active:
            SMSProvider.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


@admin.register(EmailProvider)
class EmailProviderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider_type",
        "from_email",
        "active_status",
        "created_at",
    )
    list_filter = ("provider_type", "is_active")
    search_fields = ("name", "from_email")
    readonly_fields = ("created_at",)

    def active_status(self, obj):
        if obj.is_active:
            return format_html('<b style="color: green;">ACTIVE</b>')
        return format_html('<b style="color: red;">INACTIVE</b>')

    active_status.short_description = "Status"

    def save_model(self, request, obj, form, change):
        if obj.is_active:
            EmailProvider.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


# =====================================================
# 2. SMS PRICING (ADMIN SETS PRICE PER SMS)
# =====================================================

@admin.register(SMSPricing)
class SMSPricingAdmin(admin.ModelAdmin):
    list_display = (
        "price_per_sms",
        "currency",
        "active_status",
        "updated_at",
    )
    list_filter = ("is_active",)
    readonly_fields = ("updated_at",)

    def active_status(self, obj):
        if obj.is_active:
            return format_html('<b style="color: green;">ACTIVE</b>')
        return format_html('<b style="color: red;">INACTIVE</b>')

    active_status.short_description = "Status"

    def save_model(self, request, obj, form, change):
        """
        Ensure ONLY ONE pricing is active at a time
        """
        if obj.is_active:
            SMSPricing.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


# =====================================================
# 3. VENDOR SMS WALLET (WITH TOPUP ACTION)
# =====================================================

class TopUpSMSForm(forms.Form):
    sms_units = forms.IntegerField(
        min_value=1,
        label='SMS Units to Add',
        help_text='Number of SMS units to credit to this vendor'
    )
    note = forms.CharField(
        required=False,
        max_length=200,
        label='Note (optional)',
        help_text='Internal note for this top-up (e.g. "Manual top-up by admin")'
    )


@admin.register(VendorSMSWallet)
class VendorSMSWalletAdmin(admin.ModelAdmin):
    list_display = (
        'vendor',
        'balance_units',
        'balance_amount',
        'updated_at',
    )
    search_fields = (
        'vendor__company_name',
        'vendor__user__username',
    )
    readonly_fields = (
        'vendor',
        'balance_units',
        'balance_amount',
        'updated_at',
    )
    actions = ['topup_sms_units']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:wallet_id>/topup/', self.admin_site.admin_view(self.topup_view), name='sms_wallet_topup'),
        ]
        return custom + urls

    def topup_sms_units(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Please select exactly one vendor wallet to top up.', level=messages.WARNING)
            return
        wallet = queryset.first()
        return redirect(f'topup/')
    topup_sms_units.short_description = 'Top up SMS units for selected vendor'

    def topup_view(self, request, wallet_id):
        wallet = VendorSMSWallet.objects.select_related('vendor').get(pk=wallet_id)

        if request.method == 'POST':
            form = TopUpSMSForm(request.POST)
            if form.is_valid():
                units = form.cleaned_data['sms_units']
                with transaction.atomic():
                    w = VendorSMSWallet.objects.select_for_update().get(pk=wallet_id)
                    w.balance_units += units
                    w.save(update_fields=['balance_units', 'updated_at'])
                    SMSPurchase.objects.create(
                        vendor=w.vendor,
                        amount_paid=0,
                        sms_units_credited=units,
                        price_per_sms=0,
                        status='SUCCESS',
                    )
                self.message_user(request, f'Successfully credited {units} SMS units to {wallet.vendor.company_name}. New balance: {w.balance_units} units.')
                return redirect('../../')
        else:
            form = TopUpSMSForm()

        context = {
            **self.admin_site.each_context(request),
            'title': f'Top Up SMS — {wallet.vendor.company_name}',
            'wallet': wallet,
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/sms/topup_sms.html', context)


# =====================================================
# 4. SMS PURCHASES (AUDIT TRAIL)
# =====================================================

@admin.register(SMSPurchase)
class SMSPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "vendor",
        "amount_paid",
        "sms_units_credited",
        "price_per_sms",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "vendor__company_name",
        "vendor__user__username",
    )
    readonly_fields = (
        "vendor",
        "amount_paid",
        "sms_units_credited",
        "price_per_sms",
        "status",
        "created_at",
    )

    def has_add_permission(self, request):
        # Created by system after payment
        return False

    def has_delete_permission(self, request, obj=None):
        # Keep audit trail intact
        return False


# =====================================================
# 5. SMS LOGS + MANUAL SEND
# =====================================================

class ManualSMSForm(forms.Form):
    phone = forms.CharField(
        max_length=20,
        label='Phone Number',
        help_text='e.g. 0771234567 or 256771234567'
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        label='Message',
        max_length=500,
    )


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'vendor',
        'phone',
        'voucher_code',
        'status_badge',
        'failure_reason',
        'provider',
        'payment_amount',
        'payment_package',
    )
    list_filter = ('status', 'provider', 'created_at', 'vendor')
    search_fields = ('phone', 'voucher_code', 'vendor__company_name')
    readonly_fields = (
        'vendor',
        'phone',
        'voucher_code',
        'payment',
        'message',
        'provider',
        'status',
        'failure_reason',
        'created_at',
    )
    date_hierarchy = 'created_at'
    change_list_template = 'admin/sms/smslog/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('send-manual/', self.admin_site.admin_view(self.send_manual_sms_view), name='sms_send_manual'),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_send_sms_button'] = True
        return super().changelist_view(request, extra_context=extra_context)

    def send_manual_sms_view(self, request):
        from accounts.models import Vendor
        from sms.services.sms_gateway import send_sms

        if request.method == 'POST':
            form = ManualSMSForm(request.POST)
            vendor_id = request.POST.get('vendor_id')
            vendor = Vendor.objects.filter(id=vendor_id).first() if vendor_id else None

            if form.is_valid():
                phone = form.cleaned_data['phone']
                message = form.cleaned_data['message']
                try:
                    send_sms(
                        vendor=vendor,
                        phone=phone,
                        message=message,
                        purpose='MANUAL_ADMIN',
                    )
                    self.message_user(request, f'SMS sent successfully to {phone}.')
                except Exception as e:
                    self.message_user(request, f'SMS failed: {e}', level=messages.ERROR)
                return redirect('../')
        else:
            form = ManualSMSForm()

        from accounts.models import Vendor
        context = {
            **self.admin_site.each_context(request),
            'title': 'Send Manual SMS',
            'form': form,
            'vendors': Vendor.objects.filter(status='ACTIVE').order_by('company_name'),
            'opts': self.model._meta,
        }
        return render(request, 'admin/sms/send_manual_sms.html', context)

    def status_badge(self, obj):
        if obj.status == 'SENT':
            return format_html('<b style="color:green">✓ Sent</b>')
        return format_html('<b style="color:red">✗ {}</b>', obj.status)
    status_badge.short_description = 'Status'

    def payment_amount(self, obj):
        if obj.payment:
            return f'UGX {obj.payment.amount}'
        return '-'
    payment_amount.short_description = 'Amount'

    def payment_package(self, obj):
        if obj.payment and obj.payment.package:
            return obj.payment.package.name
        return '-'
    payment_package.short_description = 'Package'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

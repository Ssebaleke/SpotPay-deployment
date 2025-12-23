from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import HotspotLocation


@admin.register(HotspotLocation)
class HotspotLocationAdmin(admin.ModelAdmin):
    """
    Admin interface for managing hotspot locations.
    UUID is exposed as read-only for client support and portal access.
    """

    # =========================
    # Admin list configuration
    # =========================
    list_display = (
        'site_name',
        'vendor',
        'short_uuid',
        'location_type',
        'status_badge',
        'created_at',
        'row_actions',
    )

    list_filter = (
        'status',
        'location_type',
        'created_at',
        'vendor__company_name',
    )

    search_fields = (
        'site_name',
        'address',
        'town_city',
        'vendor__company_name',
        'uuid',
    )

    # =========================
    # Read-only fields
    # =========================
    readonly_fields = (
        'uuid_display',
        'portal_url_display',
        'created_at',
        'updated_at',
        'approved_at',
    )

    actions = (
        'approve_locations',
        'reject_locations',
        'suspend_locations',
    )

    # =========================
    # Form layout
    # =========================
    fieldsets = (
        (_('Location Information'), {
            'fields': (
                'vendor',
                'site_name',
                'location_type',
                'address',
                'town_city',
            )
        }),
        (_('Portal Configuration'), {
            'fields': (
                'uuid_display',
                'portal_url_display',
                'location_slug',
                'max_concurrent_users',
                'is_active',
            )
        }),
        (_('Approval Status'), {
            'fields': (
                'status',
                'approved_by',
                'approved_at',
                'rejection_reason',
            )
        }),
        (_('Admin Notes'), {
            'fields': ('admin_notes',),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )

    # =========================
    # Custom display methods
    # =========================

    @admin.display(description=_('UUID'))
    def uuid_display(self, obj):
        """
        Full UUID, copy-friendly.
        """
        return format_html(
            '<code style="user-select: all;">{}</code>',
            obj.uuid
        )

    @admin.display(description=_('UUID'))
    def short_uuid(self, obj):
        """
        Short UUID preview for list view.
        """
        return str(obj.uuid)[:8]

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {
            'PENDING': 'warning',
            'ACTIVE': 'success',
            'REJECTED': 'danger',
            'SUSPENDED': 'secondary',
        }
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            colors.get(obj.status, 'secondary'),
            obj.get_status_display(),
        )

    @admin.display(description=_('Portal URL'))
    def portal_url_display(self, obj):
        if obj.portal_url:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.portal_url,
                obj.portal_url,
            )
        return _("Not generated yet")

    @admin.display(description=_('Actions'))
    def row_actions(self, obj):
        buttons = []

        if obj.status == 'PENDING':
            buttons.append(
                f'<a class="button" href="?approve={obj.id}">{_("Approve")}</a>'
            )
            buttons.append(
                f'<a class="button" href="?reject={obj.id}">{_("Reject")}</a>'
            )

        elif obj.status == 'ACTIVE':
            buttons.append(
                f'<a class="button" href="?suspend={obj.id}">{_("Suspend")}</a>'
            )

        else:
            buttons.append(
                f'<a class="button" href="?approve={obj.id}">{_("Activate")}</a>'
            )

        return format_html(' '.join(buttons))

    # =========================
    # Admin bulk actions
    # =========================

    @admin.action(description=_('Approve selected locations'))
    def approve_locations(self, request, queryset):
        count = 0
        for location in queryset:
            if location.status != 'ACTIVE':
                location.approve(request.user)
                count += 1

        if count:
            self.message_user(
                request,
                _(f'Successfully approved {count} location(s).'),
                messages.SUCCESS,
            )

    @admin.action(description=_('Reject selected locations'))
    def reject_locations(self, request, queryset):
        count = 0
        for location in queryset:
            if location.status != 'REJECTED':
                location.reject(_('Rejected by admin'))
                count += 1

        if count:
            self.message_user(
                request,
                _(f'Successfully rejected {count} location(s).'),
                messages.WARNING,
            )

    @admin.action(description=_('Suspend selected locations'))
    def suspend_locations(self, request, queryset):
        count = 0
        for location in queryset:
            if location.status == 'ACTIVE':
                location.suspend(_('Suspended by admin'))
                count += 1

        if count:
            self.message_user(
                request,
                _(f'Successfully suspended {count} location(s).'),
                messages.ERROR,
            )

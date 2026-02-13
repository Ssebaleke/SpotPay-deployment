from django.contrib import admin
from .models import PortalTemplate

@admin.register(PortalTemplate)
class PortalTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "uploaded_at", "is_active")
    list_filter = ("is_active",)

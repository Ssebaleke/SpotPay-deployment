"""
URL configuration for Billing project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.admin import admin_site

# Copy all models registered on default admin to our custom admin site
def _copy_registry():
    for model, model_admin in admin.site._registry.items():
        if model not in admin_site._registry:
            admin_site.register(model, type(model_admin))

_copy_registry()

urlpatterns = [
    path('admin/', admin_site.urls),
    path('', include('accounts.urls')),
    path('locations/', include('hotspot.urls')),
    path('packages/', include('packages.urls')),
    path('voucher/', include('vouchers.urls')),
    path('ads/', include('ads.urls')),
    path('wallets/', include('wallets.urls')),
    path("api/", include("portal_api.urls")),
    path('payments/', include('payments.urls')),
    path("sms/", include("sms.urls")),
    path('analytics/', include('analytics.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

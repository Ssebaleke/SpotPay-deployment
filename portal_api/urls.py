from django.urls import path
from .views import (
    portal_data,
    portal_download_page,
    download_portal_zip,
    portal_buy,          # 👈 add this
)

urlpatterns = [
    # =========================
    # MAIN CAPTIVE PORTAL API
    # =========================
    path(
        "portal/<uuid:uuid>/",
        portal_data,
        name="portal_api",
    ),

    # =========================
    # FALLBACK BUY PAGE (NO JS)
    # =========================
    path(
        "portal/<uuid:uuid>/buy/",
        portal_buy,
        name="portal_buy",
    ),

    # =========================
    # PORTAL DOWNLOAD (VENDOR)
    # =========================
    path(
        "portal-download/<uuid:location_uuid>/",
        portal_download_page,
        name="portal_download_page",
    ),

    path(
        "portal/<uuid:location_uuid>/download/",
        download_portal_zip,
        name="portal_zip_download",
    ),
]

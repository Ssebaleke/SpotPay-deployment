from django.urls import path
from .views import (
    portal_data,
    portal_download_page,
    download_portal_zip,
    portal_buy,                 # fallback HTML
    portal_buy_api,             # JSON buy endpoint
    portal_payment_status,      # polling endpoint
)

urlpatterns = [
    # =========================
    # MAIN CAPTIVE PORTAL API
    # =========================
    path(
        "<uuid:uuid>/",
        portal_data,
        name="portal_api",
    ),

    # =========================
    # JS BUY (JSON)
    # =========================
    path(
        "<uuid:uuid>/buy/",
        portal_buy_api,
        name="portal_buy_api",
    ),

    # =========================
    # PAYMENT STATUS POLLING
    # =========================
    path(
        "payments/status/<str:reference>/",
        portal_payment_status,
        name="portal_payment_status",
    ),

    # =========================
    # FALLBACK BUY PAGE (HTML)
    # =========================
    path(
        "<uuid:uuid>/buy-page/",
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
        "<uuid:location_uuid>/download/",
        download_portal_zip,
        name="portal_zip_download",
    ),
]
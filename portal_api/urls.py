from django.urls import path
from . import views

urlpatterns = [
    # =========================
    # MAIN CAPTIVE PORTAL API
    # =========================
    path(
        "<uuid:uuid>/",
        views.portal_data,
        name="portal_api",
    ),

    # =========================
    # JS BUY (JSON)
    # =========================
    path(
        "<uuid:uuid>/buy/",
        views.portal_buy_api,
        name="portal_buy_api",
    ),

    # =========================
    # PAYMENT STATUS POLLING
    # =========================
    path(
        "payments/status/<str:reference>/",
        views.portal_payment_status,
        name="portal_payment_status",
    ),

    # =========================
    # FALLBACK BUY PAGE (HTML)
    # =========================
    path(
        "<uuid:uuid>/buy-page/",
        views.portal_buy,
        name="portal_buy_page",
    ),

    # =========================
    # PORTAL DOWNLOAD (VENDOR)
    # =========================
    path(
        "portal-download/<uuid:location_uuid>/",
        views.portal_download_page,
        name="portal_download_page",
    ),

    path(
        "<uuid:location_uuid>/download/",
        views.download_portal_zip,
        name="portal_zip_download",
    ),
]
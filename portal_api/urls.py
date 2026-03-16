from django.urls import path
from .views import (
    portal_data,
    portal_download_page,
    download_portal_zip,
    portal_buy,
    portal_buy_api,
    portal_payment_status,
    mikrotik_setup_script,
)

urlpatterns = [
    path("portal/<uuid:uuid>/", portal_data, name="portal_api"),
    path("portal/<uuid:uuid>/buy-api/", portal_buy_api, name="portal_buy_api"),
    path("portal/payments/status/<str:reference>/", portal_payment_status, name="portal_payment_status"),
    path("portal/<uuid:uuid>/buy/", portal_buy, name="portal_buy"),
    path("portal-download/<uuid:location_uuid>/", portal_download_page, name="portal_download_page"),
    path("portal/<uuid:location_uuid>/download/", download_portal_zip, name="portal_zip_download"),
    path("portal/<uuid:location_uuid>/mikrotik-script/", mikrotik_setup_script, name="mikrotik_setup_script"),
]
from django.urls import path
from .views import (
    portal_data,
    portal_download_page,
    download_portal_zip,
    portal_buy,
    portal_buy_api,
    mikrotik_setup_script,
    location_portal_view,
    register_vpn,
)

urlpatterns = [
    path("portal/<uuid:uuid>/", portal_data, name="portal_api"),
    path("portal/<uuid:uuid>/buy-api/", portal_buy_api, name="portal_buy_api"),
    path("portal/<uuid:uuid>/buy/", portal_buy, name="portal_buy"),
    path("portal/<uuid:uuid>/portal/", location_portal_view, name="location_portal_view"),
    path("portal-download/<uuid:location_uuid>/", portal_download_page, name="portal_download_page"),
    path("portal/<uuid:location_uuid>/download/", download_portal_zip, name="portal_zip_download"),
    path("portal/<uuid:location_uuid>/mikrotik-script/", mikrotik_setup_script, name="mikrotik_setup_script"),
    path("register-vpn/", register_vpn, name="register_vpn"),
]
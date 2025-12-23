from django.urls import path
from .views import portal_data, portal_download_page, download_portal_zip

urlpatterns = [
    path(
        "portal/<uuid:uuid>/",
        portal_data,
        name="portal_api"
    ),

    path(
        "portal-download/<uuid:location_uuid>/",
        portal_download_page,
        name="portal_download_page"
    ),

    path(
        "portal/<uuid:location_uuid>/download/",
        download_portal_zip,
        name="portal_zip_download"
    ),
]

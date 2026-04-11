# hotspot/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.locations_list, name='locations_list'),
    path('add/', views.add_location, name='add_location'),
    path('status/<int:location_id>/', views.location_status, name='location_status'),
    path('locations/', views.locations_list, name='locations_list'),
    path('locations/<int:location_id>/edit/', views.edit_location, name='edit_location'),
    path('locations/<int:location_id>/save-login-type/', views.save_login_type, name='save_login_type'),
    path('voucher-generator/', views.voucher_generator, name='voucher_generator'),
    path('voucher-generator/<int:location_id>/open/', views.mikhmon_redirect, name='mikhmon_redirect'),
    path('<int:location_id>/vpn-setup/', views.vpn_setup, name='vpn_setup'),
    path('<int:location_id>/vpn-script.rsc', views.vpn_script, name='vpn_script'),
    path('<int:location_id>/vpn-reset/', views.vpn_reset, name='vpn_reset'),
    path('<int:location_id>/vpn-register/', views.vpn_manual_register, name='vpn_manual_register'),
    path('<int:location_id>/ovpn-download/', views.ovpn_download, name='ovpn_download'),
    path('dns-setup/', views.dns_setup, name='dns_setup'),
    path('dns-setup/<int:location_id>/save/', views.save_dns, name='save_dns'),
]

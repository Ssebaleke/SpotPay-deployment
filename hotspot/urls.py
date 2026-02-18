# hotspot/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.locations_list, name='locations_list'),
    path('add/', views.add_location, name='add_location'),
    path('status/<int:location_id>/', views.location_status, name='location_status'),
    path('locations/', views.locations_list, name='locations_list'),
    path('locations/<int:location_id>/edit/', views.edit_location, name='edit_location'),
]

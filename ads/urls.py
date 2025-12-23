from django.urls import path
from . import views

urlpatterns = [
    path('', views.ads_list, name='ads_list'),
    path('delete/<int:id>/', views.delete_ad, name='delete_ad'),

    # Captive portal
    path('portal/<int:location_id>/', views.portal_ads, name='portal_ads'),
]

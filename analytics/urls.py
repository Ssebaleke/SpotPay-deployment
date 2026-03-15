from django.urls import path
from . import views

urlpatterns = [
    path('', views.analytics_dashboard, name='analytics_dashboard'),
    path('data/', views.analytics_data, name='analytics_data'),
]

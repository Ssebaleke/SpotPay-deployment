from django.urls import path
from . import views

urlpatterns = [
    path('', views.learning_page, name='learning_page'),
    path('login/', views.vendor_login, name='vendor_login'),
    path('register/', views.vendor_register, name='vendor_register'),
    path('logout/', views.vendor_logout, name='vendor_logout'),  # ✅ ADD THIS
    path('dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
]


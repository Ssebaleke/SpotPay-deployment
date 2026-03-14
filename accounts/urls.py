from django.urls import path
from . import views

urlpatterns = [
    path('', views.learning_page, name='learning_page'),
    path('login/', views.vendor_login, name='vendor_login'),
    path('register/', views.vendor_register, name='vendor_register'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('logout/', views.vendor_logout, name='vendor_logout'),
    path('dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('profile/', views.vendor_profile, name='vendor_profile'),
    path('change-password/', views.vendor_change_password, name='vendor_change_password'),
    path("pay-subscription/", views.pay_subscription, name="pay_subscription"),
]


from django.urls import path
from . import views

urlpatterns = [
    path('', views.learning_page, name='learning_page'),
    path('login/', views.vendor_login, name='vendor_login'),
    path('register/', views.vendor_register, name='vendor_register'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/vendors/<int:vendor_id>/approve/', views.admin_approve_vendor, name='admin_approve_vendor'),
    path('admin-dashboard/vendors/<int:vendor_id>/reject/', views.admin_reject_vendor, name='admin_reject_vendor'),
    path('admin-dashboard/withdrawals/<int:withdrawal_id>/approve/', views.admin_approve_withdrawal, name='admin_approve_withdrawal'),
    path('admin-dashboard/withdrawals/<int:withdrawal_id>/reject/', views.admin_reject_withdrawal, name='admin_reject_withdrawal'),
    path('logout/', views.vendor_logout, name='vendor_logout'),
    path('dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('profile/', views.vendor_profile, name='vendor_profile'),
    path('change-password/', views.vendor_change_password, name='vendor_change_password'),
    path("pay-subscription/", views.pay_subscription, name="pay_subscription"),
    path('forgot-password/', views.password_reset_request, name='password_reset_request'),
    path('reset-password/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
]


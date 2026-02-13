from django.urls import path
from . import views

urlpatterns = [
    path('', views.wallet_dashboard, name='wallet_dashboard'),
    path('locked/', views.wallet_locked, name='wallet_locked'),
    path('reset-password/', views.wallet_password_reset_request, name='wallet_password_reset_request'),
    path('setup-password/<uuid:token>/', views.setup_wallet_password, name='wallet_setup_password'),
    path('auth/', views.wallet_authenticate, name='wallet_authenticate'),
    path('otp/send/', views.wallet_send_otp, name='wallet_send_otp'),
    path('otp/verify/', views.wallet_verify_otp, name='wallet_verify_otp'),
    path('withdraw/', views.wallet_withdraw, name='wallet_withdraw'),
    path('lock/', views.wallet_lock, name='wallet_lock'),
    path(
    'reset-password/auth/',
    views.wallet_password_reset_from_auth,
    name='wallet_password_reset_from_auth'
),
]

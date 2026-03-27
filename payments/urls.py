from django.urls import path
from . import views
from . import ipn_views

app_name = "payments"

urlpatterns = [
    # Payment initiation (generic — works for MakyPay and Yoo)
    path("initiate/", views.initiate_payment, name="initiate_payment"),

    # MakyPay webhook
    path("webhook/makypay/", views.payment_callback, name="payment_callback"),

    # Yo! Payments IPN endpoints
    # InstantNotificationUrl → /payments/webhook/yoo/ipn/
    path("webhook/yoo/ipn/", ipn_views.yoo_ipn, name="yoo_ipn"),
    # FailureNotificationUrl → /payments/webhook/yoo/failure/
    path("webhook/yoo/failure/", ipn_views.yoo_failure_notification, name="yoo_failure_notification"),

    # KwaPay IPN
    path("webhook/kwa/ipn/", ipn_views.kwa_ipn, name="kwa_ipn"),

    # KwaPay manual verify (polls check_status for stuck PENDING payments)
    path("kwa/verify/<str:reference>/", ipn_views.kwa_verify, name="kwa_verify"),

    # Payment status polling (used by portal.js)
    path("status/<str:reference>/", views.payment_status, name="payment_status"),

    # Post-payment redirect → auto-login on MikroTik
    path("success/<uuid:uuid>/", views.payment_success_redirect, name="payment_success_redirect"),
]

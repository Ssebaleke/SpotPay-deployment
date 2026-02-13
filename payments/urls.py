from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("initiate/", views.initiate_payment, name="initiate_payment"),
    path("webhook/makypay/", views.payment_callback, name="payment_callback"),
    path("status/<str:reference>/", views.payment_status, name="payment_status"),
    path("success/<uuid:uuid>/", views.payment_success_redirect, name="payment_success_redirect"),
]

from django.urls import path
from . import views

urlpatterns = [
    # 1️⃣ User starts payment
    path('initiate/', views.initiate_payment, name='initiate_payment'),

    # 2️⃣ Payment provider callback (NO REDIRECT HERE)
    path('callback/', views.payment_callback, name='payment_callback'),

    # 3️⃣ User-facing success page → AUTO CONNECTION happens here
    path(
        'success/<uuid:uuid>/',
        views.payment_success_redirect,
        name='payment_success'
    ),
]

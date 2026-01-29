from django.urls import path
from .views import sms_topup

app_name = "sms"

urlpatterns = [
    path("topup/", sms_topup, name="sms_topup"),
]

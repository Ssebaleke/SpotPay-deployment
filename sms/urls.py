from django.urls import path
from .views import sms_topup, sms_pricing_info, sms_wallet_info, ugsms_balance

app_name = "sms"

urlpatterns = [
    path("topup/", sms_topup, name="sms_topup"),
    path("pricing/", sms_pricing_info, name="sms_pricing_info"),
    path("wallet/", sms_wallet_info, name="sms_wallet_info"),
    path("provider/balance/", ugsms_balance, name="ugsms_balance"),
]

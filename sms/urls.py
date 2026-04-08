from django.urls import path
from .views import sms_topup, sms_pricing_info, sms_wallet_info, ugsms_balance, sms_send_bulk, sms_logs, sell_voucher_sms, test_email, resend_sms

app_name = "sms"

urlpatterns = [
    path("topup/", sms_topup, name="sms_topup"),
    path("pricing/", sms_pricing_info, name="sms_pricing_info"),
    path("wallet/", sms_wallet_info, name="sms_wallet_info"),
    path("send/bulk/", sms_send_bulk, name="sms_send_bulk"),
    path("provider/balance/", ugsms_balance, name="ugsms_balance"),
    path("logs/", sms_logs, name="sms_logs"),
    path("logs/<int:log_id>/resend/", resend_sms, name="resend_sms"),
    path("sell-voucher/", sell_voucher_sms, name="sell_voucher_sms"),
    path("test-email/", test_email, name="test_email"),
]

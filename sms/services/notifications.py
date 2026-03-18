from sms.services.email_gateway import send_email
from sms.services.sms_gateway import send_sms


def notify_vendor_payment_received(payment):
    vendor = payment.vendor
    if not vendor:
        return

    subject = "Payment Received - SpotPay"
    text = (
        f"Hello {vendor.company_name},\n\n"
        f"A payment of {payment.currency} {payment.amount} was received successfully.\n"
        f"Reference: {payment.provider_reference or payment.uuid}\n"
        f"Date: {payment.completed_at or payment.initiated_at}\n\n"
        "SpotPay"
    )
    html = (
        f"<p>Hello {vendor.company_name},</p>"
        f"<p>A payment of <strong>{payment.currency} {payment.amount}</strong> was received successfully.</p>"
        f"<p>Reference: <strong>{payment.provider_reference or payment.uuid}</strong></p>"
        f"<p>Date: {payment.completed_at or payment.initiated_at}</p>"
        "<p>SpotPay</p>"
    )

    send_email(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        html=html,
        text=text,
    )

    if vendor.business_phone:
        send_sms(
            vendor=vendor,
            phone=vendor.business_phone,
            message=f"Payment received: {payment.currency} {payment.amount}. Ref {payment.provider_reference or payment.uuid}",
            purpose="PAYMENT_RECEIVED",
        )


def notify_vendor_receipt(payment):
    """Email receipt to vendor for SMS purchase or subscription payment."""
    vendor = payment.vendor
    if not vendor:
        return

    purpose_label = {
        "SMS_PURCHASE": "SMS Units Purchase",
        "SUBSCRIPTION": "Subscription Payment",
        "TRANSACTION": "WiFi Transaction",
    }.get(payment.purpose, payment.purpose)

    subject = f"Payment Receipt - {purpose_label} - SpotPay"
    html = (
        f"<p>Hello {vendor.company_name},</p>"
        f"<p>Your payment has been received successfully.</p>"
        f"<table style='border-collapse:collapse; width:100%; font-size:14px;'>"
        f"<tr><td style='padding:8px; border:1px solid #ddd;'><strong>Type</strong></td><td style='padding:8px; border:1px solid #ddd;'>{purpose_label}</td></tr>"
        f"<tr><td style='padding:8px; border:1px solid #ddd;'><strong>Amount</strong></td><td style='padding:8px; border:1px solid #ddd;'>{payment.currency} {payment.amount}</td></tr>"
        f"<tr><td style='padding:8px; border:1px solid #ddd;'><strong>Reference</strong></td><td style='padding:8px; border:1px solid #ddd;'>{payment.provider_reference or payment.uuid}</td></tr>"
        f"<tr><td style='padding:8px; border:1px solid #ddd;'><strong>Date</strong></td><td style='padding:8px; border:1px solid #ddd;'>{payment.completed_at or payment.initiated_at}</td></tr>"
        f"</table>"
        f"<p>Thank you for using SpotPay.</p>"
    )

    send_email(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        html=html,
    )



    subject = "Your SpotPay Vendor Account is Approved"
    text = (
        f"Hello {vendor.company_name},\n\n"
        "Your vendor account has been approved and is now active.\n"
        "You can now log in and start using SpotPay.\n\n"
        "SpotPay"
    )
    html = (
        f"<p>Hello {vendor.company_name},</p>"
        "<p>Your vendor account has been <strong>approved</strong> and is now active.</p>"
        "<p>You can now log in and start using SpotPay.</p>"
        "<p>SpotPay</p>"
    )

    send_email(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        html=html,
        text=text,
    )




def notify_withdrawal_status(withdrawal, status_text):
    if not withdrawal.wallet or not withdrawal.wallet.vendor:
        return

    vendor = withdrawal.wallet.vendor
    subject = f"Withdrawal {status_text} - SpotPay"
    text = (
        f"Hello {vendor.company_name},\n\n"
        f"Your withdrawal request of UGX {withdrawal.amount} is now {status_text}.\n"
        f"Reference: {withdrawal.reference}\n\n"
        "SpotPay"
    )

    send_email(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        text=text,
    )

    if vendor.business_phone:
        send_sms(
            vendor=vendor,
            phone=vendor.business_phone,
            message=f"Withdrawal {status_text}: UGX {withdrawal.amount}. Ref {withdrawal.reference}",
            purpose="WITHDRAWAL_STATUS",
        )

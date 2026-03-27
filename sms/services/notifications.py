import logging
from sms.services.email_gateway import send_email
from sms.services.sms_gateway import send_sms

logger = logging.getLogger(__name__)


def _send(*, to_email, subject, html=None, text=None, context=""):
    """Wrapper — logs failures so nothing is silently swallowed."""
    ok, resp = send_email(to_email=to_email, subject=subject, html=html, text=text)
    if not ok:
        logger.error(f"Email failed [{context}] to={to_email} subject='{subject}' reason={resp}")
    return ok, resp


def notify_vendor_payment_received(payment):
    vendor = payment.vendor
    if not vendor:
        return

    subject = "Payment Received - SpotPay"
    html = (
        f"<p>Hello {vendor.company_name},</p>"
        f"<p>A payment of {payment.currency} {payment.amount} has been received.</p>"
        f"<p>Reference: {payment.provider_reference or payment.uuid}</p>"
        f"<p>Date: {payment.completed_at or payment.initiated_at}</p>"
        f"<p>SpotPay</p>"
    )
    text = (
        f"Hello {vendor.company_name},\n\n"
        f"Payment received: {payment.currency} {payment.amount}\n"
        f"Reference: {payment.provider_reference or payment.uuid}\n"
        f"Date: {payment.completed_at or payment.initiated_at}\n\n"
        "SpotPay"
    )

    _send(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        html=html,
        text=text,
        context="notify_vendor_payment_received",
    )

    if vendor.business_phone:
        if vendor.sms_notifications_enabled:
            try:
                sms_wallet = vendor.sms_wallet
                if sms_wallet.balance > 0:
                    send_sms(
                        vendor=vendor,
                        phone=vendor.business_phone,
                        message=f"Payment received: {payment.currency} {payment.amount}. Ref {payment.provider_reference or payment.uuid}",
                        purpose="PAYMENT_RECEIVED",
                    )
            except Exception:
                pass


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

    subject = f"Receipt - {purpose_label} - SpotPay"
    html = (
        f"<p>Hello {vendor.company_name},</p>"
        f"<p>Your payment has been received.</p>"
        f"<p>Type: {purpose_label}</p>"
        f"<p>Amount: {payment.currency} {payment.amount}</p>"
        f"<p>Reference: {payment.provider_reference or payment.uuid}</p>"
        f"<p>Date: {payment.completed_at or payment.initiated_at}</p>"
        f"<p>Thank you for using SpotPay.</p>"
    )

    _send(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        html=html,
        context="notify_vendor_receipt",
    )


def notify_vendor_approval(vendor):
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
    _send(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        html=html,
        text=text,
        context="notify_vendor_approval",
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

    _send(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        text=text,
        context="notify_withdrawal_status",
    )

    if vendor.business_phone:
        send_sms(
            vendor=vendor,
            phone=vendor.business_phone,
            message=f"Withdrawal {status_text}: UGX {withdrawal.amount}. Ref {withdrawal.reference}",
            purpose="WITHDRAWAL_STATUS",
        )


def notify_withdrawal_receipt(withdrawal):
    """Send withdrawal receipt to vendor after successful withdrawal."""
    if not withdrawal.wallet or not withdrawal.wallet.vendor:
        return

    vendor = withdrawal.wallet.vendor
    subject = "Withdrawal Receipt - SpotPay"
    html = (
        f"<p>Hello {vendor.company_name},</p>"
        f"<p>Your withdrawal has been processed successfully. Here are the details:</p>"
        f"<table style='border-collapse:collapse; width:100%; font-size:14px;'>"
        f"<tr><td style='padding:8px; border:1px solid #ddd;'><strong>Amount</strong></td><td style='padding:8px; border:1px solid #ddd;'>UGX {withdrawal.amount}</td></tr>"
        f"<tr><td style='padding:8px; border:1px solid #ddd;'><strong>Payout Method</strong></td><td style='padding:8px; border:1px solid #ddd;'>{withdrawal.get_payout_method_display()}</td></tr>"
        f"<tr><td style='padding:8px; border:1px solid #ddd;'><strong>Account Number</strong></td><td style='padding:8px; border:1px solid #ddd;'>{withdrawal.payout_phone}</td></tr>"
        f"<tr><td style='padding:8px; border:1px solid #ddd;'><strong>Account Name</strong></td><td style='padding:8px; border:1px solid #ddd;'>{withdrawal.payout_name}</td></tr>"
        f"<tr><td style='padding:8px; border:1px solid #ddd;'><strong>Reference</strong></td><td style='padding:8px; border:1px solid #ddd;'>{withdrawal.reference}</td></tr>"
        f"<tr><td style='padding:8px; border:1px solid #ddd;'><strong>Date & Time</strong></td><td style='padding:8px; border:1px solid #ddd;'>{withdrawal.created_at.strftime('%d %b %Y, %H:%M:%S')} UTC</td></tr>"
        f"</table>"
        f"<p>If you did not make this withdrawal, contact support immediately.</p>"
        f"<p>SpotPay Team</p>"
    )
    text = (
        f"Hello {vendor.company_name},\n\n"
        f"Withdrawal Receipt:\n"
        f"Amount: UGX {withdrawal.amount}\n"
        f"Method: {withdrawal.get_payout_method_display()}\n"
        f"Account: {withdrawal.payout_phone}\n"
        f"Name: {withdrawal.payout_name}\n"
        f"Reference: {withdrawal.reference}\n"
        f"Date: {withdrawal.created_at.strftime('%d %b %Y, %H:%M:%S')} UTC\n\n"
        "SpotPay Team"
    )
    _send(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        html=html,
        text=text,
        context="notify_withdrawal_receipt",
    )


def notify_vendor_registration(vendor):
    """Welcome email to vendor after they register — before approval."""
    subject = "Welcome to SpotPay — Registration Received"
    html = (
        f"<p>Hello {vendor.company_name},</p>"
        f"<p>Thank you for registering on <strong>SpotPay</strong>.</p>"
        f"<p>Your account is currently <strong>pending review</strong>. "
        f"Our team will review your details and notify you once approved.</p>"
        f"<p>If you have any questions, reply to this email or contact support@spotpay.it.com</p>"
        f"<p>SpotPay Team</p>"
    )
    _send(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        html=html,
        context="notify_vendor_registration",
    )


def notify_admin_new_vendor(vendor):
    """Alert admin when a new vendor registers — requires ADMIN_EMAIL env var."""
    import os
    admin_email = os.getenv("ADMIN_EMAIL", "").strip()
    if not admin_email:
        logger.warning("notify_admin_new_vendor: ADMIN_EMAIL not set, skipping admin alert")
        return

    subject = f"New Vendor Registration — {vendor.company_name}"
    html = (
        f"<p>A new vendor has registered on SpotPay and is awaiting approval.</p>"
        f"<table style='border-collapse:collapse; font-size:14px;'>"
        f"<tr><td style='padding:6px 12px; border:1px solid #ddd;'><strong>Company</strong></td><td style='padding:6px 12px; border:1px solid #ddd;'>{vendor.company_name}</td></tr>"
        f"<tr><td style='padding:6px 12px; border:1px solid #ddd;'><strong>Contact</strong></td><td style='padding:6px 12px; border:1px solid #ddd;'>{vendor.contact_person}</td></tr>"
        f"<tr><td style='padding:6px 12px; border:1px solid #ddd;'><strong>Email</strong></td><td style='padding:6px 12px; border:1px solid #ddd;'>{vendor.business_email}</td></tr>"
        f"<tr><td style='padding:6px 12px; border:1px solid #ddd;'><strong>Phone</strong></td><td style='padding:6px 12px; border:1px solid #ddd;'>{vendor.business_phone}</td></tr>"
        f"<tr><td style='padding:6px 12px; border:1px solid #ddd;'><strong>Registered</strong></td><td style='padding:6px 12px; border:1px solid #ddd;'>{vendor.created_at}</td></tr>"
        f"</table>"
        f"<p>Log in to the admin dashboard to approve or reject this vendor.</p>"
    )
    _send(
        to_email=admin_email,
        subject=subject,
        html=html,
        context="notify_admin_new_vendor",
    )


def notify_subscription_expiry(location, days_left):
    """Warn vendor their location subscription is expiring soon or has expired."""
    vendor = location.vendor
    if days_left < 0:
        subject = f"Subscription Expired — {location.site_name}"
        html = (
            f"<p>Hello {vendor.company_name},</p>"
            f"<p>Your subscription for <strong>{location.site_name}</strong> has <strong style='color:#dc2626;'>expired</strong>.</p>"
            f"<p>Your hotspot is now <strong>inactive</strong>. Clients can no longer purchase vouchers at this location.</p>"
            f"<p>Please renew your subscription immediately to restore service.</p>"
            f"<p><a href='https://spotpay.it.com/payments/subscription/' style='background:#4361ee;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;'>Renew Now</a></p>"
            f"<p>SpotPay Team</p>"
        )
    else:
        subject = f"Subscription Expiring in {days_left} Day(s) — {location.site_name}"
        html = (
            f"<p>Hello {vendor.company_name},</p>"
            f"<p>Your subscription for <strong>{location.site_name}</strong> expires in <strong>{days_left} day(s)</strong>.</p>"
            f"<p>Renew now to avoid service interruption.</p>"
            f"<p><a href='https://spotpay.it.com/payments/subscription/' style='background:#4361ee;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;'>Renew Subscription</a></p>"
            f"<p>SpotPay Team</p>"
        )
    _send(
        to_email=vendor.business_email or vendor.user.email,
        subject=subject,
        html=html,
        context="notify_subscription_expiry",
    )

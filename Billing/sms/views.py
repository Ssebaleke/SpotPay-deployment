from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.contrib import messages

from payments.views import initiate_payment


@login_required
def sms_topup(request):
    if request.method == "POST":
        amount = request.POST.get("amount")
        phone = request.POST.get("phone")

        if not amount or not phone:
            messages.error(request, "Amount and phone number are required.")
            return redirect("sms:sms_topup")

        # Build a mutable POST copy for payment initiation
        post_data = request.POST.copy()
        post_data["payer_type"] = "VENDOR"
        post_data["purpose"] = "SMS_TOPUP"
        post_data["vendor_id"] = str(request.user.vendor.id)
        post_data["amount"] = amount
        post_data["phone"] = phone

        request.POST = post_data

        response = initiate_payment(request)

        if response.status_code != 200:
            messages.error(request, "Payment initiation failed.")
            return redirect("sms:sms_topup")

        messages.success(
            request,
            "Payment request sent. Approve it on your phone."
        )
        return redirect("vendor_dashboard")

    return render(request, "sms/topup.html")

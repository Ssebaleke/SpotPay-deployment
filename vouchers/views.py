import csv
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction

from .models import Voucher
from packages.models import Package


@login_required
def voucher_list(request):
    """
    List vouchers for the logged-in vendor
    + Handle CSV upload from Mikhmon
    """

    vendor = request.user.vendor

    # Packages owned by this vendor
    packages = Package.objects.filter(
        location__vendor=vendor,
        is_active=True
    )

    # Remaining vouchers (stock)
    vouchers = Voucher.objects.filter(
        package__location__vendor=vendor
    ).select_related(
        'package',
        'package__location'
    ).order_by('-created_at')

    # Handle CSV upload
    if request.method == 'POST':
        package_id = request.POST.get('package')
        csv_file = request.FILES.get('csv_file')

        if not package_id or not csv_file:
            messages.error(request, "Please select a package and upload a CSV file.")
            return redirect('voucher_list')

        package = get_object_or_404(
            Package,
            id=package_id,
            location__vendor=vendor
        )

        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)

        created_count = 0
        skipped_count = 0

        for row in reader:
            # Mikhmon CSV headers
            code = (
                row.get('Username')
                or row.get('Password')
                or row.get('username')
                or row.get('password')
            )

            if not code:
                skipped_count += 1
                continue

            voucher, created = Voucher.objects.get_or_create(
                code=code.strip(),
                defaults={'package': package}
            )

            # Repair old vouchers without package
            if not created and voucher.package is None:
                voucher.package = package
                voucher.save()

            if created:
                created_count += 1

        messages.success(
            request,
            f"{created_count} vouchers uploaded successfully. "
            f"{skipped_count} rows skipped."
        )

        return redirect('voucher_list')

    return render(request, 'vouchers/voucher_list.html', {
        'packages': packages,
        'vouchers': vouchers
    })


@login_required
def edit_voucher(request, id):
    """
    Edit a single voucher (vendor-safe)
    """

    voucher = get_object_or_404(
        Voucher,
        id=id,
        package__location__vendor=request.user.vendor
    )

    if request.method == 'POST':
        new_code = request.POST.get('code')

        if not new_code:
            messages.error(request, "Voucher code cannot be empty.")
            return redirect('voucher_edit', id=id)

        voucher.code = new_code.strip()
        voucher.save()

        messages.success(request, "Voucher updated successfully.")
        return redirect('voucher_list')

    return render(request, 'vouchers/edit_voucher.html', {
        'voucher': voucher
    })


@login_required
def delete_voucher(request, id):
    """
    Manual delete (vendor-safe)
    """

    voucher = get_object_or_404(
        Voucher,
        id=id,
        package__location__vendor=request.user.vendor
    )

    voucher.delete()
    messages.success(request, "Voucher deleted successfully.")
    return redirect('voucher_list')


# ============================================================
# 🔥 AUTOMATIC VOUCHER ISSUE (CONSUME & DELETE)
# ============================================================

def issue_voucher(package):
    """
    Issue ONE voucher for a package and DELETE it immediately.
    This prevents reuse completely.
    """

    with transaction.atomic():
        voucher = (
            Voucher.objects
            .select_for_update()
            .filter(package=package)
            .first()
        )

        if not voucher:
            return None

        code = voucher.code
        voucher.delete()

    return code


@login_required
def issue_voucher_demo(request, package_id):
    """
    DEMO / TEMP view to test voucher issuing
    (replace later with payment success logic)
    """

    package = get_object_or_404(
        Package,
        id=package_id,
        location__vendor=request.user.vendor
    )

    voucher_code = issue_voucher(package)

    if not voucher_code:
        messages.error(request, "No vouchers available for this package.")
        return redirect('voucher_list')

    # Later you will:
    # send_sms(phone_number, voucher_code)

    messages.success(request, f"Voucher issued: {voucher_code}")
    return redirect('voucher_list')

import csv
import random
import string
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.http import HttpResponse

from .models import Voucher, VoucherBatch, VoucherBatchDeletionLog
from packages.models import Package


def _generate_code(length=8):
    """Generate a random alphanumeric voucher code like Mikhmon."""
    chars = string.ascii_lowercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=length))
        if not Voucher.objects.filter(code=code).exists():
            return code


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
        'package__location',
        'batch'
    ).order_by('-created_at')

    filter_package_id = request.GET.get('package')
    if filter_package_id:
        vouchers = vouchers.filter(package_id=filter_package_id)

    batches = VoucherBatch.objects.filter(
        package__location__vendor=vendor
    ).select_related(
        'package',
        'package__location'
    ).annotate(
        vouchers_count=Count('vouchers'),
        used_count=Count('vouchers', filter=Q(vouchers__status='USED')),
        unused_count=Count('vouchers', filter=Q(vouchers__status='UNUSED')),
    )

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

        # Reuse existing batch for this package, or create new one
        batch = VoucherBatch.objects.filter(package=package).first()
        if not batch:
            batch = VoucherBatch.objects.create(
                package=package,
                uploaded_by=request.user,
                source_filename=getattr(csv_file, 'name', ''),
            )

        decoded_file = csv_file.read().decode('utf-8-sig').splitlines()

        if not decoded_file:
            messages.error(request, "CSV file is empty.")
            return redirect('voucher_list')

        reader = csv.DictReader(decoded_file)

        codes = []
        for row in reader:
            row = {k.strip().lower(): (v.strip() if v else '') for k, v in row.items()}
            code = (
                row.get('username')
                or row.get('password')
                or row.get('code')
                or row.get('voucher')
                or row.get('voucher_code')
                or (list(row.values())[0] if row else None)
            )
            if code and code.strip():
                codes.append(code.strip())

        if not codes:
            messages.error(request, "No valid voucher codes found in CSV.")
            batch.delete()
            return redirect('voucher_list')

        # exclude already existing codes
        existing_codes = set(
            Voucher.objects.filter(code__in=codes).values_list('code', flat=True)
        )
        new_codes = [c for c in codes if c not in existing_codes]
        skipped_count = len(codes) - len(new_codes)

        with transaction.atomic():
            Voucher.objects.bulk_create([
                Voucher(code=c, package=package, batch=batch)
                for c in new_codes
            ], ignore_conflicts=True)

        created_count = len(new_codes)

        batch.total_uploaded = created_count
        if created_count == 0:
            if not batch.vouchers.exists():
                batch.delete()
            messages.warning(request,
                f"0 new vouchers added — all {skipped_count} codes already exist in the system. "
                f"Delete the existing batch first if you want to re-upload."
            )
            return redirect('voucher_list')
        else:
            batch.total_uploaded = (batch.vouchers.count())
            batch.save(update_fields=['total_uploaded'])
            from django.core.cache import cache
            cache.delete(f'portal_data_{package.location.uuid}')

        messages.success(
            request,
            f"{created_count} vouchers uploaded successfully. "
            f"{skipped_count} rows skipped."
        )

        return redirect('voucher_list')

    paginator = Paginator(vouchers, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'vouchers/voucher_list.html', {
        'packages': packages,
        'page_obj': page_obj,
        'batches': batches,
        'filter_package_id': filter_package_id,
    })


@login_required
def delete_voucher_batch(request, id):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('voucher_list')

    batch = get_object_or_404(
        VoucherBatch,
        id=id,
        package__location__vendor=request.user.vendor
    )

    if batch.vouchers.filter(status='USED').exists():
        messages.error(request, 'This batch contains used vouchers and cannot be deleted.')
        return redirect('voucher_list')

    with transaction.atomic():
        from payments.models import PaymentVoucher
        from django.core.cache import cache
        PaymentVoucher.objects.filter(voucher__batch=batch).delete()
        deleted_count, _ = batch.vouchers.all().delete()

        # Clear portal cache so package disappears immediately
        if batch.package.location_id:
            cache.delete(f'portal_data_{batch.package.location.uuid}')

        VoucherBatchDeletionLog.objects.create(
            batch_reference=batch.id,
            package=batch.package,
            vendor=request.user.vendor,
            deleted_by=request.user,
            source_filename=batch.source_filename,
            vouchers_deleted_count=deleted_count,
        )

        batch.delete()

    messages.success(request, f'Batch deleted successfully. {deleted_count} voucher(s) removed.')
    return redirect('voucher_list')


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


@login_required
def generate_vouchers(request):
    if request.method != 'POST':
        return redirect('voucher_list')

    vendor = request.user.vendor
    package_id = request.POST.get('package')
    quantity = request.POST.get('quantity', '').strip()

    if not package_id or not quantity:
        messages.error(request, "Please select a package and enter quantity.")
        return redirect('voucher_list')

    try:
        quantity = int(quantity)
        if quantity < 1 or quantity > 500:
            raise ValueError
    except ValueError:
        messages.error(request, "Quantity must be between 1 and 500.")
        return redirect('voucher_list')

    package = get_object_or_404(Package, id=package_id, location__vendor=vendor)

    batch = VoucherBatch.objects.create(
        package=package,
        uploaded_by=request.user,
        source_filename='generated',
        total_uploaded=quantity,
    )

    codes = []
    with transaction.atomic():
        for _ in range(quantity):
            code = _generate_code()
            codes.append(Voucher(code=code, package=package, batch=batch))
        Voucher.objects.bulk_create(codes)

    messages.success(request, f"{quantity} vouchers generated successfully for {package.name}.")

    # If download requested, return CSV
    if request.POST.get('download') == '1':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="vouchers-{package.name}-{batch.id}.csv"'
        writer = csv.writer(response)
        writer.writerow(['username', 'password'])
        for v in Voucher.objects.filter(batch=batch):
            writer.writerow([v.code, v.code])
        return response

    return redirect('voucher_list')


@login_required
def download_batch_csv(request, batch_id):
    vendor = request.user.vendor
    batch = get_object_or_404(VoucherBatch, id=batch_id, package__location__vendor=vendor)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="vouchers-{batch.package.name}-{batch.id}.csv"'
    writer = csv.writer(response)
    writer.writerow(['username', 'password'])
    for v in Voucher.objects.filter(batch=batch).order_by('code'):
        writer.writerow([v.code, v.code])
    return response




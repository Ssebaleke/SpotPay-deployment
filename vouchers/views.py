import csv
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.core.paginator import Paginator

from .models import Voucher, VoucherBatch, VoucherBatchDeletionLog
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
        'package__location',
        'batch'
    ).order_by('-created_at')

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

        created_count = 0
        skipped_count = 0

        for row in reader:
            # Normalize row keys to lowercase for flexible matching
            row = {k.strip().lower(): (v.strip() if v else '') for k, v in row.items()}
            code = (
                row.get('username')
                or row.get('password')
                or row.get('code')
                or row.get('voucher')
                or row.get('voucher_code')
                or (list(row.values())[0] if row else None)
            )

            if not code:
                skipped_count += 1
                continue

            voucher, created = Voucher.objects.get_or_create(
                code=code.strip(),
                defaults={
                    'package': package,
                    'batch': batch,
                }
            )

            if not created and voucher.package is None:
                voucher.package = package
                voucher.save()

            if created:
                created_count += 1
            else:
                skipped_count += 1

        batch.total_uploaded = created_count
        if created_count == 0:
            batch.delete()
            messages.warning(request,
                f"0 new vouchers added — all {skipped_count} codes already exist in the system. "
                f"Delete the existing batch first if you want to re-upload."
            )
            return redirect('voucher_list')
        else:
            batch.save(update_fields=['total_uploaded'])

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
        deleted_count, _ = batch.vouchers.all().delete()

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




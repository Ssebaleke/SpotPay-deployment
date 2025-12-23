from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

from .forms import VendorRegistrationForm
from .models import Vendor


def learning_page(request):
    """
    Public landing / learning page.
    """
    return render(request, 'accounts/home.html')


def vendor_register(request):
    if request.method == 'POST':
        form = VendorRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Registration successful! Please wait for admin approval.'
            )
            return redirect('vendor_login')
    else:
        form = VendorRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def vendor_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            user = authenticate(username=username, password=password)

            # Extra safety: block inactive users early
            if user is not None and user.is_active:
                try:
                    vendor = user.vendor
                    if vendor.status == 'ACTIVE':
                        login(request, user)
                        return redirect('vendor_dashboard')
                    else:
                        messages.error(
                            request,
                            'Your account is not approved yet or has been suspended.'
                        )
                except Vendor.DoesNotExist:
                    messages.error(request, 'This account is not a vendor.')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def vendor_dashboard(request):
    try:
        vendor = request.user.vendor

        if vendor.status != 'ACTIVE' or not request.user.is_active:
            messages.error(
                request,
                'Your account is not approved or has been suspended.'
            )
            return redirect('vendor_login')

    except Vendor.DoesNotExist:
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendor_login')

    return render(request, 'accounts/dashboard.html', {'vendor': vendor})


@login_required
def vendor_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('vendor_login')

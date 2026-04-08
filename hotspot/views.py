from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings

from .models import HotspotLocation
from .forms import HotspotLocationForm


# =====================================================
# LIST LOCATIONS
# =====================================================

@login_required
def locations_list(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        vendor = request.user.vendor
    except:
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendor_login')
    
    locations = vendor.locations.all().order_by('-created_at')

    return render(request, 'hotspot/locations.html', {
        'locations': locations,
        'vendor': vendor
    })


# =====================================================
# ADD LOCATION
# =====================================================

@login_required
def add_location(request):
    # Staff users cannot add locations
    if request.user.is_staff:
        messages.warning(request, 'Staff users cannot add locations.')
        return redirect('locations_list')
    
    if request.method == 'POST':
        form = HotspotLocationForm(request.POST)

        if form.is_valid():
            location = form.save(commit=False)
            location.vendor = request.user.vendor

            location.hotspot_dns = request.POST.get('hotspot_dns', '').strip() or 'hot.spot'

            location.save()

            messages.success(
                request,
                f'Location "{location.site_name}" submitted for approval.'
            )

        return redirect('locations_list')

    return redirect('locations_list')


# =====================================================
# EDIT LOCATION
# =====================================================

@login_required
def edit_location(request, location_id):
    # Staff users cannot edit locations
    if request.user.is_staff:
        messages.warning(request, 'Staff users cannot edit locations.')
        return redirect('locations_list')
    
    try:
        vendor = request.user.vendor
    except:
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendor_login')

    location = get_object_or_404(
        HotspotLocation,
        id=location_id,
        vendor=vendor
    )

    if request.method == "POST":
        location.site_name = request.POST.get('site_name', location.site_name).strip()
        location.location_type = request.POST.get('location_type', location.location_type)
        location.town_city = request.POST.get('town_city', location.town_city).strip()
        location.address = request.POST.get('address', location.address).strip()
        location.login_type = request.POST.get('login_type', location.login_type)
        location.save(update_fields=['site_name', 'location_type', 'town_city', 'address', 'login_type'])
        messages.success(request, f'Location "{location.site_name}" updated successfully.')
        return redirect("locations_list")
    return render(
        request,
        "hotspot/location_form.html",
        {"location": location}
    )


# =====================================================
# LOCATION STATUS (AJAX)
# =====================================================

@login_required
def location_status(request, location_id):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        vendor = request.user.vendor
    except:
        return JsonResponse({'error': 'Not a vendor'}, status=403)

    location = get_object_or_404(
        HotspotLocation,
        id=location_id,
        vendor=vendor
    )

    return JsonResponse({
        'status': location.status,
        'status_display': location.get_status_display(),
        'portal_url': location.portal_url or '',
        'location_uuid': str(location.uuid),
        'rejection_reason': location.rejection_reason or '',
    })


# =====================================================
# VOUCHER GENERATOR — location picker
# =====================================================

@login_required
def voucher_generator(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        vendor = request.user.vendor
    except:
        return redirect('vendor_login')
    locations = vendor.locations.filter(status='ACTIVE').order_by('site_name')
    return render(request, 'hotspot/voucher_generator.html', {
        'vendor': vendor,
        'locations': locations,
    })


# =====================================================
# MIKHMON REDIRECT — per location
# =====================================================

@login_required
def mikhmon_redirect(request, location_id):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        vendor = request.user.vendor
    except:
        return redirect('vendor_login')

    location = get_object_or_404(HotspotLocation, id=location_id, vendor=vendor, status='ACTIVE')

    if not location.mikhmon_session:
        return redirect('vpn_setup', location_id=location_id)

    mikhmon_url = getattr(settings, 'MIKHMON_URL', '').rstrip('/')
    mikhmon_user = getattr(settings, 'MIKHMON_USER', 'admin')
    mikhmon_pass = getattr(settings, 'MIKHMON_PASS', '')

    if not mikhmon_url:
        messages.error(request, 'Mikhmon is not configured on this server. Please contact support.')
        return redirect('voucher_generator')

    from django.http import HttpResponseRedirect
    return HttpResponseRedirect(
        f"{mikhmon_url}/index.php?admin&login"
        f"&user={mikhmon_user}&pass={mikhmon_pass}"
        f"&session={location.mikhmon_session}"
    )


# =====================================================
# VPN SETUP PAGE — shown when mikhmon_session is empty
# =====================================================

@login_required
def vpn_setup(request, location_id):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        vendor = request.user.vendor
    except:
        return redirect('vendor_login')

    location = get_object_or_404(HotspotLocation, id=location_id, vendor=vendor, status='ACTIVE')

    # Generate credentials once and save
    if not location.vpn_api_user:
        import random, string
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        location.vpn_api_user = f'spotpay_{suffix}'
        location.vpn_api_password = suffix
        location.save(update_fields=['vpn_api_user', 'vpn_api_password'])

    script_url = f"{settings.SITE_URL}/locations/{location_id}/vpn-script.rsc"
    one_liner = (
        f'/tool fetch url="{script_url}" dst-path="spotpay-setup.rsc" mode=https; '
        f'/import spotpay-setup.rsc'
    )

    return render(request, 'hotspot/vpn_setup.html', {
        'vendor': vendor,
        'location': location,
        'one_liner': one_liner,
        'script_url': script_url,
    })


# =====================================================
# VPN SCRIPT — serves the .rsc file to MikroTik
# =====================================================

def vpn_script(request, location_id):
    """Public endpoint — MikroTik fetches this directly via /tool fetch."""
    from django.http import HttpResponse

    location = get_object_or_404(HotspotLocation, id=location_id, status='ACTIVE')

    if not location.vpn_api_user:
        return HttpResponse('# Error: VPN not initialized for this location', content_type='text/plain')

    vpn_server_ip     = getattr(settings, 'VPN_SERVER_IP', '')
    vpn_server_port   = getattr(settings, 'VPN_SERVER_PORT', '51820')
    vpn_public_key    = getattr(settings, 'VPN_SERVER_PUBLIC_KEY', '')
    vpn_iface         = getattr(settings, 'VPN_INTERFACE_NAME', 'wg0')
    vpn_subnet        = getattr(settings, 'VPN_SUBNET', '10.10.0')

    # Assign VPN IP based on location ID (10.10.0.X, starting at .2)
    vpn_client_ip = f"{vpn_subnet}.{location.id + 1}"
    vpn_server_peer_ip = f"{vpn_subnet}.1"

    api_user = location.vpn_api_user
    api_pass = location.vpn_api_password

    script = f"""# SpotPay VPN Setup Script
# Location: {location.site_name}
# Generated by SpotPay — do not edit manually

# ── 1. Create SpotPay API user with full access ──
/user add name={api_user} password={api_pass} group=full comment="SpotPay API User"

# ── 2. Enable API service on port 8728 ──
/ip service set api disabled=no port=8728

# ── 3. Add WireGuard interface ──
/interface wireguard add name={vpn_iface} listen-port={vpn_server_port} comment="SpotPay VPN"

# ── 4. Assign IP to WireGuard interface ──
/ip address add address={vpn_client_ip}/24 interface={vpn_iface}

# ── 5. Add VPS as WireGuard peer ──
/interface wireguard peers add interface={vpn_iface} public-key="{vpn_public_key}" endpoint-address={vpn_server_ip} endpoint-port={vpn_server_port} allowed-address={vpn_server_peer_ip}/32 persistent-keepalive=25 comment="SpotPay VPS"

:put "SpotPay VPN setup complete. User={api_user} VPN-IP={vpn_client_ip}"
"""

    # Mark as configured
    if not location.vpn_configured:
        location.vpn_configured = True
        location.save(update_fields=['vpn_configured'])

    return HttpResponse(script, content_type='text/plain; charset=utf-8')


@login_required
def save_login_type(request, location_id):
    try:
        vendor = request.user.vendor
    except:
        return redirect('vendor_login')

    location = get_object_or_404(HotspotLocation, id=location_id, vendor=vendor)

    if request.method == 'POST':
        login_type = request.POST.get('login_type', '').strip()
        valid = [choice[0] for choice in HotspotLocation.LOGIN_TYPES]
        if login_type in valid:
            location.login_type = login_type
            location.save(update_fields=['login_type'])
            messages.success(request, f'Login type updated to "{location.get_login_type_display()}".')
        else:
            messages.error(request, 'Invalid login type.')

    next_url = request.POST.get('next') or 'locations_list'
    return redirect(next_url)


# =====================================================
# DNS SETUP PAGE
# =====================================================

@login_required
def dns_setup(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        vendor = request.user.vendor
    except:
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendor_login')

    locations = vendor.locations.filter(status='ACTIVE').order_by('-created_at')

    return render(request, 'hotspot/dns_setup.html', {
        'locations': locations,
        'vendor': vendor,
        'site_url': settings.SITE_URL,
    })


# =====================================================
# SAVE DNS (POST per location)
# =====================================================

@login_required
def save_dns(request, location_id):
    if request.user.is_staff:
        messages.warning(request, 'Staff users cannot edit DNS settings.')
        return redirect('dns_setup')

    try:
        vendor = request.user.vendor
    except:
        return redirect('vendor_login')

    location = get_object_or_404(HotspotLocation, id=location_id, vendor=vendor)

    if request.method == 'POST':
        dns = request.POST.get('hotspot_dns', '').strip() or 'hot.spot'
        location.hotspot_dns = dns
        location.save(update_fields=['hotspot_dns'])
        messages.success(request, f'DNS for "{location.site_name}" updated to {dns}.')

    return redirect('dns_setup')

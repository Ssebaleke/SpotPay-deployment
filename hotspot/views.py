from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

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
    return render(request, 'hotspot/locations.html', {'locations': locations, 'vendor': vendor})


# =====================================================
# ADD LOCATION
# =====================================================

@login_required
def add_location(request):
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
            messages.success(request, f'Location "{location.site_name}" submitted for approval.')
        return redirect('locations_list')

    return redirect('locations_list')


# =====================================================
# EDIT LOCATION
# =====================================================

@login_required
def edit_location(request, location_id):
    if request.user.is_staff:
        messages.warning(request, 'Staff users cannot edit locations.')
        return redirect('locations_list')

    try:
        vendor = request.user.vendor
    except:
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendor_login')

    location = get_object_or_404(HotspotLocation, id=location_id, vendor=vendor)

    if request.method == 'POST':
        location.site_name = request.POST.get('site_name', location.site_name).strip()
        location.location_type = request.POST.get('location_type', location.location_type)
        location.town_city = request.POST.get('town_city', location.town_city).strip()
        location.address = request.POST.get('address', location.address).strip()
        location.login_type = request.POST.get('login_type', location.login_type)
        location.save(update_fields=['site_name', 'location_type', 'town_city', 'address', 'login_type'])
        messages.success(request, f'Location "{location.site_name}" updated successfully.')
        return redirect('locations_list')

    return render(request, 'hotspot/location_form.html', {'location': location})


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

    location = get_object_or_404(HotspotLocation, id=location_id, vendor=vendor)
    return JsonResponse({
        'status': location.status,
        'status_display': location.get_status_display(),
        'portal_url': location.portal_url or '',
        'location_uuid': str(location.uuid),
        'rejection_reason': location.rejection_reason or '',
    })


# =====================================================
# VOUCHER GENERATOR
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
    return render(request, 'hotspot/voucher_generator.html', {'vendor': vendor, 'locations': locations})


# =====================================================
# MIKHMON REDIRECT
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
    if not mikhmon_url:
        messages.error(request, 'Mikhmon is not configured. Please contact support.')
        return redirect('voucher_generator')

    return HttpResponseRedirect(mikhmon_url)


# =====================================================
# VPN SETUP PAGE
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

    # Generate API credentials once
    if not location.vpn_api_user:
        import random, string
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        location.vpn_api_user = f'spotpay_{suffix}'
        location.vpn_api_password = password
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
# OVPN CERT PART DOWNLOADS — serves individual PEM
# parts for ROS v6 (CA, cert, key served separately)
# =====================================================

def _extract_ovpn_block(config, tag):
    """Extract content between <tag>...</tag> from .ovpn config."""
    import re
    m = re.search(rf'<{tag}>(.*?)</{tag}>', config, re.DOTALL)
    return m.group(1).strip() if m else ''


def ovpn_download(request, location_id):
    """Serves the full .ovpn for manual use."""
    location = get_object_or_404(HotspotLocation, id=location_id, status='ACTIVE')
    if not location.ovpn_client_config:
        return HttpResponse('# OpenVPN config not generated yet', content_type='text/plain')
    response = HttpResponse(location.ovpn_client_config, content_type='application/x-openvpn-profile')
    response['Content-Disposition'] = f'attachment; filename="spotpay-{location.id}.ovpn"'
    return response


def ovpn_ca(request, location_id):
    location = get_object_or_404(HotspotLocation, id=location_id, status='ACTIVE')
    pem = _extract_ovpn_block(location.ovpn_client_config, 'ca')
    return HttpResponse(pem or '# not found', content_type='text/plain')


def ovpn_cert(request, location_id):
    location = get_object_or_404(HotspotLocation, id=location_id, status='ACTIVE')
    # The cert block contains bag attributes + the actual cert — strip to just the cert
    import re
    raw = _extract_ovpn_block(location.ovpn_client_config, 'cert')
    # Keep only the -----BEGIN CERTIFICATE----- block
    m = re.search(r'(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)', raw, re.DOTALL)
    pem = m.group(1) if m else raw
    return HttpResponse(pem or '# not found', content_type='text/plain')


def ovpn_key(request, location_id):
    location = get_object_or_404(HotspotLocation, id=location_id, status='ACTIVE')
    pem = _extract_ovpn_block(location.ovpn_client_config, 'key')
    return HttpResponse(pem or '# not found', content_type='text/plain')


# =====================================================
# VPN SCRIPT — universal auto-detecting script
# Works on both ROS v6 (OpenVPN) and ROS v7 (WireGuard)
# =====================================================

def vpn_script(request, location_id):
    location = get_object_or_404(HotspotLocation, id=location_id, status='ACTIVE')

    if not location.vpn_api_user:
        return HttpResponse('# Error: VPN not initialized for this location', content_type='text/plain')

    api_user        = location.vpn_api_user
    api_pass        = location.vpn_api_password
    register_url    = f"{settings.SITE_URL}/api/register-vpn/"
    ca_url          = f"{settings.SITE_URL}/locations/{location_id}/ovpn-ca/"
    cert_url        = f"{settings.SITE_URL}/locations/{location_id}/ovpn-cert/"
    key_url         = f"{settings.SITE_URL}/locations/{location_id}/ovpn-key/"
    vpn_server_ip   = getattr(settings, 'VPN_SERVER_IP', '')
    vpn_server_port = getattr(settings, 'VPN_SERVER_PORT', '443')
    vpn_public_key  = getattr(settings, 'VPN_SERVER_PUBLIC_KEY', '')
    vpn_iface       = getattr(settings, 'VPN_INTERFACE_NAME', 'wg0')
    vpn_subnet      = getattr(settings, 'VPN_SUBNET', '10.8.0')
    vpn_client_ip   = f"{vpn_subnet}.{location.id + 1}"
    ovpn_client_ip  = f"10.9.0.{location.id + 1}"

    lines = [
        "# SpotPay Universal VPN Setup Script",
        f"# Location: {location.site_name}",
        "# Auto-detects RouterOS version — ROS v6 uses OpenVPN, ROS v7 uses WireGuard",
        "",
        "# 1. Create SpotPay API user (skip if exists)",
        f":if ([:len [/user find where name=\"{api_user}\"]] = 0) do={{/user add name=\"{api_user}\" password=\"{api_pass}\" group=full comment=\"SpotPay API User\"}} else={{/user set [find where name=\"{api_user}\"] password=\"{api_pass}\" group=full}}",
        "",
        "# 2. Enable API on port 8728",
        "/ip service set api disabled=no port=8728",
        "",
        "# 3. Allow API from VPN subnets (firewall)",
        f":if ([:len [/ip firewall filter find where chain=input protocol=tcp dst-port=8728 comment=\"SpotPay API\"]] = 0) do={{/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8728 src-address={vpn_subnet}.0/24 comment=\"SpotPay API\" place-before=0}}",
        f":if ([:len [/ip firewall filter find where chain=input protocol=tcp dst-port=8728 comment=\"SpotPay API v6\"]] = 0) do={{/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8728 src-address=10.9.0.0/24 comment=\"SpotPay API v6\" place-before=0}}",
        "",
        "# 4. Detect ROS major version",
        ":local rosVer [/system resource get version]",
        # Extract just the major version number (first char before the dot)
        ":local majorVer [:pick $rosVer 0 [:find $rosVer \".\"]]",
        ":local isV6 false",
        ":if ($majorVer = \"6\") do={:set isV6 true}",
        "",
        ":if ($isV6 = true) do={",
        "  # --- ROS v6: OpenVPN ---",
        f"  /tool fetch url=\"{ca_url}\" dst-path=\"spotpay-ca.pem\" mode=https",
        f"  /tool fetch url=\"{cert_url}\" dst-path=\"spotpay-cert.pem\" mode=https",
        f"  /tool fetch url=\"{key_url}\" dst-path=\"spotpay-key.pem\" mode=https",
        "  /certificate import file-name=spotpay-ca.pem passphrase=\"\"",
        "  :delay 1s",
        "  /certificate import file-name=spotpay-cert.pem passphrase=\"\"",
        "  :delay 1s",
        "  /certificate import file-name=spotpay-key.pem passphrase=\"\"",
        "  :delay 1s",
        f"  :if ([:len [/interface ovpn-client find where name=\"spotpay-vpn\"]] = 0) do={{/interface ovpn-client add name=\"spotpay-vpn\" connect-to=\"{vpn_server_ip}\" port=1194 mode=ip user=\"{api_user}\" certificate=spotpay-cert.pem_0 auth=sha1 cipher=aes256 add-default-route=no comment=\"SpotPay VPN\"}}",
        "  :delay 3s",
        f"  /tool fetch url=\"{register_url}\" http-method=post http-data=\"location_id={location.id}&public_key=ovpn&vpn_ip={ovpn_client_ip}\" keep-result=no",
        f"  :put \"SpotPay setup complete (ROS v6 OpenVPN). API user={api_user} VPN-IP={ovpn_client_ip}\"",
        "} else={",
        "  # --- ROS v7: WireGuard ---",
        f"  :if ([:len [/interface wireguard find where name=\"{vpn_iface}\"]] = 0) do={{/interface wireguard add name=\"{vpn_iface}\" listen-port=13231 comment=\"SpotPay VPN\"}}",
        f"  :if ([:len [/ip address find where address=\"{vpn_client_ip}/24\" interface=\"{vpn_iface}\"]] = 0) do={{/ip address add address=\"{vpn_client_ip}/24\" interface=\"{vpn_iface}\"}}",
        f"  :if ([:len [/interface wireguard peers find where public-key=\"{vpn_public_key}\"]] = 0) do={{/interface wireguard peers add interface=\"{vpn_iface}\" public-key=\"{vpn_public_key}\" endpoint-address=\"{vpn_server_ip}\" endpoint-port={vpn_server_port} allowed-address=\"{vpn_subnet}.0/24\" persistent-keepalive=25 comment=\"SpotPay VPS\"}}",
        "  :delay 2s",
        f"  :local pubKey [/interface wireguard get \"{vpn_iface}\" public-key]",
        f"  /tool fetch url=\"{register_url}\" http-method=post http-data=(\"location_id={location.id}&public_key=\" . $pubKey) keep-result=no",
        f"  :put (\"SpotPay setup complete (ROS v7 WireGuard). API user={api_user} VPN-IP={vpn_client_ip}\")",
        "}",
    ]
    script = "\n".join(lines)
    return HttpResponse(script, content_type='text/plain; charset=utf-8')


# =====================================================
# VPN RESET
# =====================================================

@login_required
def vpn_reset(request, location_id):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        vendor = request.user.vendor
    except:
        return redirect('vendor_login')

    location = get_object_or_404(HotspotLocation, id=location_id, vendor=vendor, status='ACTIVE')

    if request.method == 'POST':
        location.vpn_configured = False
        location.save(update_fields=['vpn_configured'])
        messages.success(request, f'VPN reset for "{location.site_name}". Run the setup script again on your MikroTik.')

    return redirect('vpn_setup', location_id=location_id)


# =====================================================
# SAVE LOGIN TYPE
# =====================================================

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
# SAVE DNS
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

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.conf import settings
import logging
import secrets

logger = logging.getLogger(__name__)

from .models import HotspotLocation
from .forms import HotspotLocationForm


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
    token = secrets.token_hex(16)
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            getattr(settings, 'VPS_SSH_HOST', ''),
            username=getattr(settings, 'VPS_SSH_USER', 'root'),
            password=getattr(settings, 'VPS_SSH_PASS', ''),
            timeout=10
        )
        ssh.exec_command(f"touch /tmp/spotpay_token_{token}")
        ssh.close()
    except Exception as e:
        logger.error(f"Token creation failed for location {location_id}: {e}")
        messages.error(request, 'Could not connect to Mikhmon. Please try again.')
        return redirect('voucher_generator')
    return HttpResponseRedirect(
        f"{mikhmon_url}/?spotpay_token={token}&session={location.mikhmon_session}"
    )


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
        location.vpn_api_user = f'spotpay_{suffix}'
        location.vpn_api_password = suffix
        location.save(update_fields=['vpn_api_user', 'vpn_api_password'])

    # Pre-generate OpenVPN config for v6 fallback
    if not location.ovpn_client_config:
        try:
            from hotspot.openvpn_config import generate_ovpn_config
            generate_ovpn_config(location)
            location.refresh_from_db()
        except Exception as e:
            logger.warning(f"OpenVPN pre-gen failed for location {location.id}: {e}")

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


def ovpn_download(request, location_id):
    location = get_object_or_404(HotspotLocation, id=location_id, status='ACTIVE')
    if not location.ovpn_client_config:
        return HttpResponse('# OpenVPN config not generated yet', content_type='text/plain')
    response = HttpResponse(location.ovpn_client_config, content_type='application/x-openvpn-profile')
    response['Content-Disposition'] = f'attachment; filename="spotpay-{location.id}.ovpn"'
    return response


def vpn_script(request, location_id):
    """
    Universal VPN setup script — auto-detects ROS v6/v7.
    Follows 5 MikroTik syntax rules:
    1. allowed-addresses (plural)
    2. :local variable before /tool fetch
    3. 10.8.0.0/16 firewall with place-before=0
    4. verNum = [:pick version 0 1] for version detection
    5. Clean-run :if [:len find] = 0 checks
    """
    location = get_object_or_404(HotspotLocation, id=location_id, status='ACTIVE')

    if not location.vpn_api_user:
        return HttpResponse('# Error: VPN not initialized for this location', content_type='text/plain')

    api_user       = location.vpn_api_user
    api_pass       = location.vpn_api_password
    register_url   = f"{settings.SITE_URL}/api/register-vpn/"
    ovpn_url       = f"{settings.SITE_URL}/locations/{location_id}/ovpn-download/"
    vps_ip         = getattr(settings, 'VPN_SERVER_IP', '')
    vps_port       = getattr(settings, 'VPN_SERVER_PORT', '443')
    wg_pubkey      = getattr(settings, 'VPN_SERVER_PUBLIC_KEY', '')
    wg_iface       = getattr(settings, 'VPN_INTERFACE_NAME', 'wg0')
    vpn_subnet     = getattr(settings, 'VPN_SUBNET', '10.8.0')
    wg_client_ip   = f"{vpn_subnet}.{location.id + 1}"
    ovpn_client_ip = f"10.9.0.{location.id + 1}"

    script = f"""# SpotPay Universal VPN Setup Script
# Location: {location.site_name} | Auto-detects ROS v6 / v7

# Rule 4: Version detection using verNum
:local verNum [:pick [/system resource get version] 0 1]

# Rule 5: Create API user (clean-run safe)
:if ([:len [/user find where name="{api_user}"]] = 0) do={{
    /user add name={api_user} password={api_pass} group=full comment="SpotPay API User"
}}

# Enable API on port 8728
/ip service set api disabled=no port=8728

# Rule 3: Firewall — allow 10.8.0.0/16 with place-before=0
:if ([:len [/ip firewall filter find where comment="SpotPay API"]] = 0) do={{
    /ip firewall filter add chain=input action=accept protocol=tcp dst-port=8728 src-address=10.8.0.0/16 comment="SpotPay API" place-before=0
}}

# Rule 4: Version branch
:if ($verNum = "7") do={{

    # ROS v7 - WireGuard
    :if ([:len [/interface wireguard find where name="{wg_iface}"]] = 0) do={{
        /interface wireguard add name={wg_iface} listen-port=13231 comment="SpotPay VPN"
    }}
    :if ([:len [/ip address find where address="{wg_client_ip}/24" and interface="{wg_iface}"]] = 0) do={{
        /ip address add address={wg_client_ip}/24 interface={wg_iface}
    }}
    :if ([:len [/interface wireguard peers find where comment="SpotPay VPS"]] = 0) do={{
        /interface wireguard peers add interface={wg_iface} public-key="{wg_pubkey}" endpoint-address={vps_ip} endpoint-port={vps_port} allowed-addresses={vpn_subnet}.0/24 persistent-keepalive=25 comment="SpotPay VPS"
    }}
    :delay 2s
    # Rule 2: local variable before fetch
    :local pk [/interface wireguard get {wg_iface} public-key]
    /tool fetch url="{register_url}" http-method=post http-data=("location_id={location.id}&public_key=" . $pk) keep-result=no
    :put "SpotPay setup complete (ROS v7). User={api_user} VPN-IP={wg_client_ip}"

}} else={{

    # ROS v6 - OpenVPN
    # Rule 2: local variable before fetch
    :local ovpnUrl "{ovpn_url}"
    /tool fetch url=$ovpnUrl dst-path="spotpay.ovpn" mode=https
    /certificate import file-name=spotpay.ovpn passphrase=""
    :delay 2s
    :if ([:len [/interface ovpn-client find where name="spotpay-vpn"]] = 0) do={{
        /interface ovpn-client add name=spotpay-vpn connect-to={vps_ip} port=1194 mode=ip user={api_user} certificate=spotpay.ovpn_0 auth=sha1 cipher=aes256 add-default-route=no comment="SpotPay VPN"
    }}
    :delay 3s
    :local ovpnIp "{ovpn_client_ip}"
    /tool fetch url="{register_url}" http-method=post http-data=("location_id={location.id}&public_key=ovpn&vpn_ip=" . $ovpnIp) keep-result=no
    :put "SpotPay setup complete (ROS v6). User={api_user} VPN-IP={ovpn_client_ip}"
}}
"""

    if not location.vpn_configured:
        location.vpn_configured = True
        location.save(update_fields=['vpn_configured'])
        try:
            from hotspot.mikhmon_config import inject_mikhmon_session
            inject_mikhmon_session(location)
        except Exception as e:
            logger.error(f"Mikhmon auto-config failed for location {location.id}: {e}")

    return HttpResponse(script, content_type='text/plain; charset=utf-8')


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

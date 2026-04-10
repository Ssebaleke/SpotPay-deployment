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

    if not location.vpn_api_user:
        import random, string
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        location.vpn_api_user = f'spotpay_{suffix}'
        location.vpn_api_password = suffix
        location.save(update_fields=['vpn_api_user', 'vpn_api_password'])

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
    Bulletproof universal VPN script.
    No backslashes. Variables at top. Single lines. Dynamic cert name.
    Works on ROS v6 (OpenVPN) and v7 (WireGuard).
    """
    location = get_object_or_404(HotspotLocation, id=location_id, status='ACTIVE')

    if not location.vpn_api_user:
        return HttpResponse('# Error: VPN not initialized', content_type='text/plain')

    u        = location.vpn_api_user
    p        = location.vpn_api_password
    site     = getattr(settings, 'SITE_URL', '').rstrip('/')
    vps_ip   = getattr(settings, 'VPN_SERVER_IP', '')
    vps_port = getattr(settings, 'VPN_SERVER_PORT', '443')
    wg_key   = getattr(settings, 'VPN_SERVER_PUBLIC_KEY', '')
    subnet   = getattr(settings, 'VPN_SUBNET', '10.8.0')
    wg_ip    = f"{subnet}.{location.id + 1}"
    ovpn_ip  = f"10.9.0.{location.id + 1}"
    loc_id   = str(location.id)
    reg_url  = f"{site}/api/register-vpn/"
    ovpn_url = f"{site}/locations/{location_id}/ovpn-download/"

    lines = [
        '{',
        f':local verNum [:pick [/system resource get version] 0 1]',
        f':local locID "{loc_id}"',
        f':local vpsIP "{vps_ip}"',
        f':local wgIP "{wg_ip}"',
        f':local ovpnIP "{ovpn_ip}"',
        f':local regURL "{reg_url}"',
        f':local wgKey "{wg_key}"',
        '',
        '# 1. Create API user',
        f':if ([:len [/user find name="{u}"]] = 0) do={{/user add name="{u}" password="{p}" group=full comment="SpotPay"}}',
        '',
        '# 2. Enable API',
        '/ip service set api disabled=no port=8728',
        '',
        '# 3. Firewall rule',
        ':if ([:len [/ip firewall filter find comment="SpotPay API"]] = 0) do={',
        '/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8728 src-address=10.8.0.0/16 comment="SpotPay API" place-before=0',
        '}',
        '',
        '# 4. ROS v7 - WireGuard',
        ':if ($verNum = "7") do={',
        ':if ([:len [/interface wireguard find name="wg0"]] = 0) do={/interface wireguard add name="wg0" listen-port=13231 comment="SpotPay VPN"}',
        ':if ([:len [/ip address find address=($wgIP . "/24")]] = 0) do={/ip address add address=($wgIP . "/24") interface="wg0"}',
        ':if ([:len [/interface wireguard peers find comment="SpotPay VPS"]] = 0) do={',
        '/interface wireguard peers add interface="wg0" public-key=$wgKey endpoint-address=$vpsIP endpoint-port=443 allowed-addresses=10.8.0.0/24 persistent-keepalive=25 comment="SpotPay VPS"',
        '}',
        ':delay 2s',
        ':local pk [/interface wireguard get [find name="wg0"] public-key]',
        '/tool fetch url=$regURL http-method=post http-data=("location_id=" . $locID . "&public_key=" . $pk) keep-result=no',
        ':put "SpotPay done (ROS v7)"',
        '',
        '# 5. ROS v6 - OpenVPN',
        '} else={',
        f':local ovpnUrl "{ovpn_url}"',
        '/tool fetch url=$ovpnUrl dst-path="spotpay.ovpn" mode=https',
        '/certificate import file-name=spotpay.ovpn passphrase=""',
        ':delay 5s',
        ':local certName [/certificate get [find name~"spotpay"] name]',
        ':if ([:len [/interface ovpn-client find name="spotpay-vpn"]] = 0) do={',
        f'/interface ovpn-client add name="spotpay-vpn" connect-to=$vpsIP port=1194 mode=ip user="{u}" certificate=$certName auth=sha1 cipher=aes256 add-default-route=no comment="SpotPay VPN"',
        '}',
        ':delay 3s',
        '/tool fetch url=$regURL http-method=post http-data=("location_id=" . $locID . "&public_key=ovpn&vpn_ip=" . $ovpnIP) keep-result=no',
        ':put "SpotPay done (ROS v6)"',
        '}',
        ':put "SpotPay Setup Finished"',
        '}',
    ]
    script = '\n'.join(lines)

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
        messages.success(request, f'VPN reset for "{location.site_name}". Run the setup script again.')
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

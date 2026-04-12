from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import logging

logger = logging.getLogger(__name__)

from pathlib import Path
import zipfile
import io
import json

from hotspot.models import HotspotLocation
from portal_api.models import PortalTemplate
from packages.models import Package
from payments.services_utils import initiate_payment
from payments.models import Payment


# =====================================================
# PORTAL DATA API (used by portal.js)
# GET  /api/portal/<uuid>/
# =====================================================

def portal_data(request, uuid):
    from django.core.cache import cache

    cache_key = f"portal_data_{uuid}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)

    location = get_object_or_404(
        HotspotLocation,
        uuid=uuid,
        status="ACTIVE",
        vendor__status="ACTIVE"
    )

    packages = location.packages.filter(
        is_active=True,
        vouchers__status='UNUSED'
    ).distinct().select_related('location')

    packages = [p for p in packages if p.is_available_now()]

    ads = location.ads.filter(is_active=True)

    data = {
        "location": {
            "name": location.site_name,
        },
        "subscription_active": location.has_active_subscription(),
        "packages": [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
            }
            for p in packages
        ] if location.has_active_subscription() else [],
        "ads": [
            {
                "type": ad.ad_type.lower(),
                "url": request.build_absolute_uri(ad.file.url),
            }
            for ad in ads
        ] if location.has_active_subscription() else [],
    }

    cache.set(cache_key, data, 60)
    return JsonResponse(data)


# =====================================================
# JS BUY API (used by portal.js Buy button)
# POST /api/portal/<uuid>/buy/
# Body JSON: { "package_id": 1, "phone": "2567xxxxxxx", "mac_address": "", "ip_address": "" }
# =====================================================

@csrf_exempt
@require_POST
def portal_buy_api(request, uuid):
    location = get_object_or_404(
        HotspotLocation,
        uuid=uuid,
        status="ACTIVE",
        vendor__status="ACTIVE"
    )

    # 🔒 enforce subscription
    if not location.has_active_subscription():
        return JsonResponse(
            {"success": False, "message": "SpotPay services unavailable for this location"},
            status=403
        )

    # parse JSON or form-urlencoded safely
    try:
        ct = (request.content_type or '').lower()
        if 'application/json' in ct:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        else:
            payload = request.POST.dict()
    except Exception:
        payload = {}

    package_id = payload.get("package_id")
    phone = (payload.get("phone") or "").strip()
    mac_address = (payload.get("mac_address") or "").strip() or None
    ip_address = (payload.get("ip_address") or "").strip() or None

    if not package_id or not phone:
        return JsonResponse(
            {"success": False, "message": "Please select a package and enter a phone number"},
            status=400
        )

    # Get package by ID
    package = get_object_or_404(
        Package,
        id=package_id,
        location=location,
        is_active=True
    )

    # Check schedule
    if not package.is_available_now():
        if package.schedule_type == 'DATE':
            msg = f"This package is only available on {package.scheduled_date.strftime('%d %b %Y')}"
        elif package.schedule_type == 'WEEKDAYS':
            day_names = dict(package.DAY_CHOICES)
            days = [day_names[d.strip()] for d in package.scheduled_days.split(',') if d.strip() in day_names]
            msg = f"This package is only available on {', '.join(days)}"
        else:
            msg = "This package is not available right now"
        return JsonResponse({"success": False, "message": msg}, status=400)

    # Ensure vouchers exist
    if not package.vouchers.filter(status="UNUSED").exists():
        return JsonResponse(
            {"success": False, "message": "This package is currently out of stock"},
            status=400
        )

    # ✅ initiate payment (your existing engine)
    try:
        result = initiate_payment(
            location=location,
            package=package,
            phone=phone,
            source="JS_PORTAL",
            mac_address=mac_address,
            ip_address=ip_address,
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "message": str(e)},
            status=400
        )

    if result.get("status_url") and not result["status_url"].startswith("http"):
        result["status_url"] = settings.SITE_URL.rstrip("/") + result["status_url"]

    return JsonResponse(result)


# =====================================================
# DOWNLOAD PORTAL ZIP (Vendor)
# =====================================================

def download_portal_zip(request, location_uuid):
    # Public endpoint — UUID is the access key, no login required
    # MikroTik /tool fetch hits this directly
    location = get_object_or_404(
        HotspotLocation,
        uuid=location_uuid,
        status="ACTIVE"
    )

    template = PortalTemplate.objects.filter(is_active=True).first()

    if not template:
        from django.http import Http404
        raise Http404

    support_phone = getattr(location.vendor, "business_phone", "") or ""

    def replace_placeholders(text):
        return (
            text
            .replace("{{API_BASE}}", settings.PORTAL_API_BASE_HTTP)
            .replace("{{LOCATION_UUID}}", str(location.uuid))
            .replace("{{BUY_URL}}", f"{settings.SITE_URL.replace('https://', 'http://')}/api/portal/{location.uuid}/buy/")
            .replace("{{SUPPORT_PHONE}}", support_phone)
            .replace("{{LOGIN_TYPE}}", location.login_type)
        )

    # --- Single file mode: ?file=login.html or ?file=js/portal.js ---
    # MikroTik fetches each file individually via this param
    file_param = request.GET.get("file", "").strip().lstrip("/")
    if file_param:
        with zipfile.ZipFile(template.zip_file.path, "r") as zf:
            match = None
            for n in zf.namelist():
                parts = n.split("/", 1)
                rel = parts[1] if len(parts) == 2 else parts[0]
                if rel == file_param:
                    match = n
                    break
            if not match:
                from django.http import Http404
                raise Http404
            content = zf.read(match)
            ext = Path(file_param).suffix.lower()
            if ext in (".html", ".js", ".css"):
                content = replace_placeholders(
                    content.decode("utf-8", errors="ignore")
                ).encode("utf-8")
            content_types = {
                ".html": "text/html", ".js": "application/javascript",
                ".css": "text/css", ".png": "image/png",
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".woff": "font/woff", ".woff2": "font/woff2",
                ".ttf": "font/ttf", ".svg": "image/svg+xml",
            }
            ct = content_types.get(ext, "application/octet-stream")
            resp = HttpResponse(content, content_type=ct)
            resp["Content-Disposition"] = f'inline; filename="{Path(file_param).name}"'
            return resp

    # --- Full ZIP mode (manual download) ---
    buffer = io.BytesIO()
    with zipfile.ZipFile(template.zip_file.path, "r") as zf_in:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf_out:
            for item in zf_in.infolist():
                parts = item.filename.split("/", 1)
                rel = parts[1] if len(parts) == 2 else parts[0]
                if not rel or rel.endswith("/"):
                    continue
                if any(rel.startswith(x) for x in (".vscode", ".git", "__MACOSX", ".DS_Store", "log.", "readme")):
                    continue
                content = zf_in.read(item.filename)
                if Path(rel).suffix.lower() in (".html", ".js", ".css"):
                    content = replace_placeholders(
                        content.decode("utf-8", errors="ignore")
                    ).encode("utf-8")
                zf_out.writestr(rel, content)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="hotspot-{location.site_name}.zip"'
    return response


# =====================================================
# VENDOR PORTAL PAGES
# =====================================================

@login_required
def portal_download_page(request, location_uuid):
    vendor = request.user.vendor

    location = get_object_or_404(
        vendor.locations,
        uuid=location_uuid,
        status="ACTIVE"
    )

    return render(
        request,
        "portal_api/portal_download.html",
        {
            "location": location,
            "site_url": settings.SITE_URL,
        }
    )


# =====================================================
# MIKROTIK SETUP SCRIPT
# GET /api/portal/<uuid>/mikrotik-script/
# Returns a plain-text RouterOS script the vendor
# pastes into MikroTik Terminal to:
#   1. Add walled-garden rules for SpotPay server
#   2. Download all hotspot portal files via /tool fetch
# =====================================================

@login_required
def mikrotik_setup_script(request, location_uuid):
    vendor = request.user.vendor

    location = get_object_or_404(
        vendor.locations,
        uuid=location_uuid,
        status="ACTIVE"
    )

    from urllib.parse import urlparse
    import socket
    parsed = urlparse(settings.SITE_URL)
    server_host = parsed.hostname or settings.SITE_URL

    try:
        server_ip = socket.gethostbyname(server_host)
    except Exception:
        server_ip = server_host

    zip_url = f"{settings.SITE_URL}/api/portal/{location.uuid}/download/"
    dns_name = location.hotspot_dns or "hot.spot"

    # Build per-file fetch commands from ZIP contents
    # This works on ALL ROS versions — no extract needed
    fetch_cmds = []
    try:
        template = PortalTemplate.objects.filter(is_active=True).first()
        if template and template.zip_file:
            with zipfile.ZipFile(template.zip_file.path, "r") as zf:
                for name in sorted(zf.namelist()):
                    if name.endswith("/"):
                        continue
                    parts = name.split("/", 1)
                    rel = parts[1] if len(parts) == 2 else parts[0]
                    if not rel:
                        continue
                    if any(rel.startswith(x) for x in (".vscode", ".git", "__MACOSX", ".DS_Store", "log.", "readme")):
                        continue
                    # Use HTTP not HTTPS — ROS v6 doesn't support modern SSL certs
                    file_url = f"http://{settings.SITE_URL.replace('https://', '').replace('http://', '')}/api/portal/{location.uuid}/download/?file={rel}"
                    dst = f"hotspot/{rel}"
                    fetch_cmds.append(f"/tool fetch url=\"{file_url}\" dst-path=\"{dst}\" mode=http")
    except Exception:
        pass

    walled_garden = (
        f":if ([:len [/ip hotspot walled-garden ip find where dst-address=\"{server_ip}\" and comment=\"SpotPay\"]] = 0) "
        f"do={{/ip hotspot walled-garden ip add action=accept comment=\"SpotPay\" dst-address={server_ip}}}; "
        f":if ([:len [/ip hotspot walled-garden find where dst-host=\"{server_host}\" and comment=\"SpotPay\"]] = 0) "
        f"do={{/ip hotspot walled-garden add action=allow comment=\"SpotPay\" dst-host={server_host}}}; "
    )

    fetch_block = "\n".join(fetch_cmds)
    done_msg = f":put \"SpotPay portal installed. DNS Name={dns_name} — set under IP > Hotspot > Server Profiles\""

    script = walled_garden + fetch_block + "; " + done_msg

    return HttpResponse(script, content_type="text/plain; charset=utf-8")


@login_required
def location_portal_view(request, uuid):
    vendor = request.user.vendor

    location = get_object_or_404(
        HotspotLocation,
        uuid=uuid,
        vendor=vendor
    )

    return render(
        request,
        "portal_api/location_portal.html",
        {"location": location}
    )


# =====================================================
# FALLBACK / ALTERNATIVE BUY PAGE (NO JS)
# (keep as-is, but now we capture the returned dict)
# =====================================================

def portal_buy(request, uuid):
    """
    Fallback voucher purchase page.
    Server-rendered. Walled-garden safe.
    """
    location = get_object_or_404(
        HotspotLocation,
        uuid=uuid,
        status="ACTIVE"
    )

    if not location.has_active_subscription():
        return HttpResponseForbidden("SpotPay services unavailable for this location")

    if request.method == "GET":
        packages = Package.objects.filter(
            location=location,
            is_active=True,
            vouchers__status="UNUSED"
        ).distinct()
        packages = [p for p in packages if p.is_available_now()]

        return render(
            request,
            "portal_api/buy.html",
            {"location": location, "packages": packages}
        )

    if request.method == "POST":
        package_id = request.POST.get("package")
        phone = request.POST.get("phone")

        packages = Package.objects.filter(
            location=location,
            is_active=True,
            vouchers__status="UNUSED"
        ).distinct()
        packages = [p for p in packages if p.is_available_now()]

        if not package_id or not phone:
            return render(
                request,
                "portal_api/buy.html",
                {
                    "location": location,
                    "packages": packages,
                    "error": "Please select a package and enter a phone number",
                }
            )

        package = get_object_or_404(
            Package,
            id=package_id,
            location=location,
            is_active=True
        )

        if not package.is_available_now():
            if package.schedule_type == 'DATE':
                error = f"This package is only available on {package.scheduled_date.strftime('%d %b %Y')}"
            elif package.schedule_type == 'WEEKDAYS':
                day_names = dict(Package.DAY_CHOICES)
                days = [day_names[d.strip()] for d in package.scheduled_days.split(',') if d.strip() in day_names]
                error = f"This package is only available on {', '.join(days)}"
            else:
                error = "This package is not available right now"
            return render(request, "portal_api/buy.html", {"location": location, "packages": packages, "error": error})

        result = initiate_payment(
            location=location,
            package=package,
            phone=phone,
            source="FALLBACK_PORTAL",
        )

        return render(
            request,
            "portal_api/buy_processing.html",
            {
                "location": location,
                "package": package,
                "phone": phone,
                "payment": result,  # ✅ use status_url / reference in template
            }
        )
        
        

# =====================================================
# PORTAL BUY FORM — plain HTML form POST
# POST /api/portal/<uuid>/buy-form/
# No CORS preflight — works on ALL phones including old Android
# Redirects to wait page after initiating payment
# =====================================================

@csrf_exempt
def portal_buy_form(request, uuid):
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)

    location = get_object_or_404(
        HotspotLocation,
        uuid=uuid,
        status='ACTIVE',
        vendor__status='ACTIVE'
    )

    if not location.has_active_subscription():
        return HttpResponse('Service unavailable for this location', status=403)

    package_id  = request.POST.get('package_id', '').strip()
    phone       = request.POST.get('phone', '').strip()
    mac_address = request.POST.get('mac_address', '').strip() or None
    ip_address  = request.POST.get('ip_address', '').strip() or None

    if not package_id or not phone:
        return HttpResponse('package_id and phone required', status=400)

    package = get_object_or_404(Package, id=package_id, location=location, is_active=True)

    if not package.is_available_now():
        return HttpResponse('Package not available right now', status=400)

    if not package.vouchers.filter(status='UNUSED').exists():
        return HttpResponse('Package out of stock', status=400)

    result = initiate_payment(
        location=location,
        package=package,
        phone=phone,
        source='FORM_PORTAL',
        mac_address=mac_address,
        ip_address=ip_address,
    )

    # Redirect to wait page — runs outside captive portal sandbox
    payment_uuid = result.get('payment_uuid', '')
    from django.shortcuts import redirect as django_redirect
    return django_redirect(f'http://spotpay.it.com/payments/wait/{payment_uuid}/')


# =====================================================
# REGISTER VPN — MikroTik callback after script runs
# POST /api/register-vpn/
# Body: location_id=<id>&public_key=<wg_pubkey>
# =====================================================

@csrf_exempt
@require_POST
def register_vpn(request):
    """
    Called by MikroTik after running the VPN setup script.
    Receives the router's WireGuard public key, then:
    1. Adds the peer to WireGuard on the VPS via SSH
    2. Saves wg config permanently (wg-quick save)
    3. Injects location into Mikhmon config.php
    4. Marks location as fully configured
    """
    location_id = request.POST.get('location_id', '').strip()
    public_key = request.POST.get('public_key', '').strip()

    # RouterOS sends + signs as spaces in form POST — restore them
    public_key = public_key.replace(' ', '+')

    if not location_id or not public_key:
        return JsonResponse({'status': 'error', 'message': 'location_id and public_key required'}, status=400)

    try:
        location = HotspotLocation.objects.get(id=location_id, status='ACTIVE')
    except HotspotLocation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Location not found'}, status=404)

    is_ovpn = (public_key == 'ovpn')
    vpn_subnet  = getattr(settings, 'VPN_SUBNET', '10.8.0')
    # v6 OpenVPN uses 10.9.0.x subnet, v7 WireGuard uses VPN_SUBNET
    if is_ovpn:
        assigned_ip = f"10.9.0.{location.id + 1}"
    else:
        assigned_ip = f"{vpn_subnet}.{location.id + 1}"

    ssh_host  = getattr(settings, 'VPS_SSH_HOST', '')
    ssh_user  = getattr(settings, 'VPS_SSH_USER', 'root')
    ssh_pass  = getattr(settings, 'VPS_SSH_PASS', '')
    vpn_iface = getattr(settings, 'VPN_INTERFACE_NAME', 'wg0')

    if not ssh_host or not ssh_pass:
        logger.error("register_vpn: VPS_SSH_HOST or VPS_SSH_PASS not set in environment")
        return JsonResponse({'status': 'error', 'message': 'VPS SSH not configured'}, status=500)

    try:
        if not is_ovpn:
            # --- ROS v7: add WireGuard peer on VPS ---
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ssh_host, username=ssh_user, password=ssh_pass, timeout=15)

            def run(cmd):
                _, stdout, stderr = client.exec_command(cmd)
                out = stdout.read().decode('utf-8', errors='ignore').strip()
                err = stderr.read().decode('utf-8', errors='ignore').strip()
                return out, err

            _, wg_err = run(f"wg set {vpn_iface} peer '{public_key}' allowed-ips {assigned_ip}/32")
            if wg_err:
                logger.warning(f"WireGuard peer add warning for location {location_id}: {wg_err}")

            _, save_err = run(f"wg-quick save {vpn_iface}")
            if save_err:
                logger.warning(f"wg-quick save warning for location {location_id}: {save_err}")

            client.close()
        # else: ROS v6 OpenVPN — VPS doesn't need peer config, tunnel is client-initiated

        # Inject into Mikhmon config.php (both v6 and v7)
        # For v6, temporarily override the VPN IP used in Mikhmon to the ovpn subnet
        if is_ovpn:
            location._ovpn_ip_override = assigned_ip

        from hotspot.mikhmon_config import inject_mikhmon_session
        ok, err = inject_mikhmon_session(location)
        if not ok:
            logger.error(f"Mikhmon inject failed for location {location_id}: {err}")

        if is_ovpn:
            del location._ovpn_ip_override

        location.vpn_configured = True
        location.save(update_fields=['vpn_configured'])

        logger.info(f"VPN registered for location {location_id} ({'OpenVPN v6' if is_ovpn else 'WireGuard v7'}) — IP {assigned_ip}")
        return JsonResponse({
            'status': 'success',
            'message': f'Location {location.site_name} is now LIVE.',
            'vpn_ip': assigned_ip,
        })

    except Exception as e:
        logger.error(f"register_vpn failed for location {location_id}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
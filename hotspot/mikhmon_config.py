"""
mikhmon_config.py
Automatically injects a new location into Mikhmon V3 config.php via SSH.
Called when vendor downloads the VPN setup script.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def inject_mikhmon_session(location):
    """
    SSH into VPS and inject location into Mikhmon config.php.
    Sets location.mikhmon_session = location.location_slug and saves.
    Returns (True, None) on success or (False, error_str) on failure.
    """
    try:
        import paramiko
    except ImportError:
        return False, "paramiko not installed"

    host = getattr(settings, 'VPS_SSH_HOST', '')
    user = getattr(settings, 'VPS_SSH_USER', 'root')
    password = getattr(settings, 'VPS_SSH_PASS', '')
    config_path = getattr(settings, 'MIKHMON_CONFIG_PATH', '/root/mikhmon-v3/include/config/config.php')
    mikhmon_url = getattr(settings, 'MIKHMON_URL', '').rstrip('/')

    if not host or not password:
        return False, "VPS SSH credentials not configured"

    # Session name = location slug (unique, URL-safe)
    session_name = location.location_slug

    # Mikhmon V3 format: session_name<|<ip<|<user<|<pass<|<hotspot<|<dns<|<no
    # ip = VPN IP assigned to this location
    vpn_subnet = getattr(settings, 'VPN_SUBNET', '10.8.0')
    vpn_ip = f"{vpn_subnet}.{location.id + 1}"

    api_user = location.vpn_api_user
    api_pass = location.vpn_api_password
    hotspot_name = location.site_name
    dns_name = location.hotspot_dns or 'hot.spot'

    new_entry = (
        f"'{session_name}' => "
        f"'{session_name}<|<{vpn_ip}<|<{api_user}<|<{api_pass}"
        f"<|<{hotspot_name}<|<{dns_name}<|<no',"
    )

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, password=password, timeout=15)

        # Read current config
        stdin, stdout, stderr = client.exec_command(f"cat {config_path}")
        content = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')

        if err and 'No such file' in err:
            client.close()
            return False, f"Mikhmon config not found at {config_path}"

        # Check if session already exists
        if session_name in content:
            client.close()
            # Already injected — just set the session name
            location.mikhmon_session = session_name
            location.save(update_fields=['mikhmon_session'])
            return True, None

        # Inject before closing ); of the array
        if ');' not in content:
            client.close()
            return False, "Mikhmon config format not recognized"

        updated = content.replace(');', f"    {new_entry}\n);", 1)

        # Write back via heredoc
        escaped = updated.replace("'", "'\\''")
        write_cmd = f"cat > {config_path} << 'SPOTPAY_EOF'\n{updated}\nSPOTPAY_EOF"
        stdin2, stdout2, stderr2 = client.exec_command(write_cmd)
        stdout2.read()
        write_err = stderr2.read().decode('utf-8', errors='ignore')
        client.close()

        if write_err:
            logger.warning(f"Mikhmon inject warning: {write_err}")

        # Save session name to location
        location.mikhmon_session = session_name
        location.save(update_fields=['mikhmon_session'])

        logger.info(f"Mikhmon session '{session_name}' injected for location {location.id}")
        return True, None

    except Exception as e:
        logger.error(f"Mikhmon SSH inject failed for location {location.id}: {e}")
        return False, str(e)

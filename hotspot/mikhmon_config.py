"""
mikhmon_config.py
Injects a new location into Mikhmon V3 config.php on the host filesystem.
Mikhmon V3 runs directly via PHP on port 8081 at /root/mikhmon-v3/

V3 config format (from live config):
$data['SESSION_KEY'] = array (
    '1'=>'SESSION_KEY!vpn_ip',
    'SESSION_KEY@|@api_user',
    'SESSION_KEY#|#api_pass',
    'SESSION_KEY%site_name',
    'SESSION_KEY^dns',
    'SESSION_KEY&UGX',
    'SESSION_KEY*10',
    'SESSION_KEY(1',
    'SESSION_KEY)',
    'SESSION_KEY=10',
    'SESSION_KEY@!@disable');
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

CONFIG_PATH = '/root/mikhmon-v3/include/config.php'


def inject_mikhmon_session(location):
    """
    SSH into VPS and inject location into Mikhmon V3 config.php on the host.
    Returns (True, None) on success or (False, error_str) on failure.
    """
    try:
        import paramiko
    except ImportError:
        return False, "paramiko not installed"

    host     = getattr(settings, 'VPS_SSH_HOST', '')
    user     = getattr(settings, 'VPS_SSH_USER', 'root')
    password = getattr(settings, 'VPS_SSH_PASS', '')

    if not host or not password:
        return False, "VPS SSH credentials not configured"

    session_key  = location.location_slug.upper().replace('-', '_')
    vpn_subnet   = getattr(settings, 'VPN_SUBNET', '10.8.0')
    vpn_ip       = "{}.{}".format(vpn_subnet, location.id + 1)
    api_user     = location.vpn_api_user
    api_pass     = location.vpn_api_password
    hotspot_name = location.site_name
    dns_name     = location.hotspot_dns or 'hot.spot'

    # V3 $data array format — matches live config exactly
    new_entry = (
        "$data['{k}'] = array ("
        "'1'=>'{k}!{ip}',"
        "'{k}@|@{u}',"
        "'{k}#|#{p}',"
        "'{k}%{name}',"
        "'{k}^{dns}',"
        "'{k}&UGX',"
        "'{k}*10',"
        "'{k}(1',"
        "'{k})',"
        "'{k}=10',"
        "'{k}@!@disable');"
    ).format(k=session_key, ip=vpn_ip, u=api_user, p=api_pass, name=hotspot_name, dns=dns_name)

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, password=password, timeout=15)

        def run(cmd):
            _, stdout, stderr = client.exec_command(cmd)
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            return out, err

        # Read current config directly from host
        out, err = run("cat '{}'".format(CONFIG_PATH))
        if not out:
            client.close()
            return False, "Could not read V3 config at {}".format(CONFIG_PATH)

        content = out

        # Already injected
        if session_key in content:
            client.close()
            location.mikhmon_session = session_key
            location.save(update_fields=['mikhmon_session'])
            logger.info("Mikhmon V3 session '{}' already exists for location {}".format(session_key, location.id))
            return True, None

        if '};' not in content:
            client.close()
            return False, "Mikhmon V3 config format not recognized — missing '};'"

        updated = content.replace('};', '};\n' + new_entry, 1)

        # Write via SFTP directly to host file
        sftp = client.open_sftp()
        with sftp.open(CONFIG_PATH, 'w') as f:
            f.write(updated)
        sftp.close()
        client.close()

        location.mikhmon_session = session_key
        location.save(update_fields=['mikhmon_session'])

        logger.info("Mikhmon V3 session '{}' injected for location {}".format(session_key, location.id))
        return True, None

    except Exception as e:
        logger.error("Mikhmon V3 inject failed for location {}: {}".format(location.id, e))
        return False, str(e)

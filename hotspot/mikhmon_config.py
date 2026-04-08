"""
mikhmon_config.py
Injects a new location into Mikhmon config.php inside the Docker container.
Uses $m_session format — the correct format for this Mikhmon version.

Working example from live config:
$m_session['vicotech-fastnet'] = 'vicotech-fastnet<|<10.8.0.5<|<spotpay_8x58i6<|<8x58i6<|<FastNet<|<hot.spot<|<no';
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

MIKHMON_CONTAINER = 'mikhmon-app'
CONFIG_PATH = '/var/www/html/config/config.php'


def inject_mikhmon_session(location):
    """
    SSH into VPS and inject location into Mikhmon config.php inside the container.
    Uses $m_session format: key<|<vpn_ip<|<api_user<|<api_pass<|<site_name<|<dns<|<no
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

    session_key  = location.location_slug          # e.g. vicotech-fastnet
    vpn_subnet   = getattr(settings, 'VPN_SUBNET', '10.8.0')
    vpn_ip       = "{}.{}".format(vpn_subnet, location.id + 1)
    api_user     = location.vpn_api_user
    api_pass     = location.vpn_api_password
    hotspot_name = location.site_name
    dns_name     = location.hotspot_dns or 'hot.spot'

    # Correct $m_session format matching live Mikhmon config
    new_entry = (
        "$m_session['{key}'] = '{key}<|<{ip}<|<{u}<|<{p}<|<{name}<|<{dns}<|<no';"
    ).format(
        key=session_key,
        ip=vpn_ip,
        u=api_user,
        p=api_pass,
        name=hotspot_name,
        dns=dns_name,
    )

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, password=password, timeout=15)

        def run(cmd):
            _, stdout, stderr = client.exec_command(cmd)
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            return out, err

        # Read current config from container
        out, err = run("docker exec {} cat '{}'".format(MIKHMON_CONTAINER, CONFIG_PATH))

        if not out:
            client.close()
            return False, "Could not read Mikhmon config at {}".format(CONFIG_PATH)

        content = out

        # Already injected — just update the session key and return
        if session_key in content:
            client.close()
            location.mikhmon_session = session_key
            location.save(update_fields=['mikhmon_session'])
            logger.info("Mikhmon session '{}' already exists for location {}".format(session_key, location.id))
            return True, None

        # Must have the closing }; to know where to inject
        if '};' not in content:
            client.close()
            return False, "Mikhmon config format not recognized — missing '};'"

        # Inject after the first }; (the security header block)
        updated = content.replace('};', ';\n' + new_entry, 1)

        # Write updated config to temp file on VPS then docker cp into container
        sftp = client.open_sftp()
        tmp_path = '/tmp/mikhmon_config_tmp.php'
        with sftp.open(tmp_path, 'w') as f:
            f.write(updated)
        sftp.close()

        out, err = run("docker cp {} {}:{}".format(tmp_path, MIKHMON_CONTAINER, CONFIG_PATH))
        if err and 'Error' in err:
            client.close()
            return False, "docker cp failed: {}".format(err)

        run("rm -f {}".format(tmp_path))
        client.close()

        location.mikhmon_session = session_key
        location.save(update_fields=['mikhmon_session'])

        logger.info("Mikhmon session '{}' injected for location {}".format(session_key, location.id))
        return True, None

    except Exception as e:
        logger.error("Mikhmon SSH inject failed for location {}: {}".format(location.id, e))
        return False, str(e)

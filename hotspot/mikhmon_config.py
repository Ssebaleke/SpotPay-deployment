"""
mikhmon_config.py
Automatically injects a new location into Mikhmon V3 config.php.
Mikhmon runs in a Docker container with no volume mount,
so we use docker exec to read/write the config file inside the container.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

MIKHMON_CONTAINER = 'mikhmon-app'


def inject_mikhmon_session(location):
    """
    SSH into VPS and inject location into Mikhmon config.php inside the container.
    Sets location.mikhmon_session = location.location_slug and saves.
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

    session_name = location.location_slug
    vpn_subnet   = getattr(settings, 'VPN_SUBNET', '10.8.0')
    vpn_ip       = f"{vpn_subnet}.{location.id + 1}"
    api_user     = location.vpn_api_user
    api_pass     = location.vpn_api_password
    hotspot_name = location.site_name
    dns_name     = location.hotspot_dns or 'hot.spot'

    # Mikhmon V3 $data array format
    session_key = session_name.upper().replace('-', '_')
    new_entry = (
        f"$data['{session_key}'] = array ("
        f"'1'=>'{session_key}!{vpn_ip}',"
        f"'{session_key}@|@{api_user}',"
        f"'{session_key}#|#{api_pass}',"
        f"'{session_key}%{hotspot_name}',"
        f"'{session_key}^{dns_name}',"
        f"'{session_key}&UGX',"
        f"'{session_key}*10',"
        f"'{session_key}(1',"
        f"'{session_key})',"
        f"'{session_key}=10',"
        f"'{session_key}@!@disable');"
    )

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, password=password, timeout=15)

        def run(cmd):
            stdin, stdout, stderr = client.exec_command(cmd)
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            return out, err

        # Find config.php inside container
        out, err = run(f"docker exec {MIKHMON_CONTAINER} find / -name 'config.php' 2>/dev/null")
        config_path = ''
        for line in out.splitlines():
            if 'mikhmon' in line.lower() or 'config/config' in line.lower():
                config_path = line.strip()
                break
        if not config_path:
            # Use known path from container inspection
            config_path = '/var/www/html/config/config.php'

        # Read current config from container
        out, err = run(f"docker exec {MIKHMON_CONTAINER} cat '{config_path}'")

        if not out:
            client.close()
            return False, f"Could not read Mikhmon config at {config_path}"

        content = out

        # Check if session already exists — prevent duplicates
        if session_key in content:
            client.close()
            location.mikhmon_session = session_key
            location.save(update_fields=['mikhmon_session'])
            return True, None

        # Inject after the security check block };  — NOT inside it
        # The file starts with: <?php if(...){header("Location:./");};
        # We inject $m_session right after };
        if '};' not in content:
            client.close()
            return False, "Mikhmon config format not recognized"

        updated = content.replace('};', f'}};
    {new_entry}', 1)

        # Write back into container using docker exec + python
        # Escape single quotes in content for shell safety
        escaped = updated.replace("'", "'\\''")
        write_cmd = f"docker exec {MIKHMON_CONTAINER} sh -c 'echo '\"'\"'{escaped}'\"'\"' > {config_path}'"

        # Safer: use docker cp approach — write to temp file on host then copy in
        sftp = client.open_sftp()
        tmp_path = '/tmp/mikhmon_config_tmp.php'
        with sftp.open(tmp_path, 'w') as f:
            f.write(updated)
        sftp.close()

        # Copy into container
        out, err = run(f"docker cp {tmp_path} {MIKHMON_CONTAINER}:{config_path}")
        if err and 'Error' in err:
            client.close()
            return False, f"docker cp failed: {err}"

        # Cleanup temp file
        run(f"rm -f {tmp_path}")

        client.close()

        # Save session key to location
        location.mikhmon_session = session_key
        location.save(update_fields=['mikhmon_session'])

        logger.info(f"Mikhmon V3 session '{session_key}' injected for location {location.id}")
        return True, None

    except Exception as e:
        logger.error(f"Mikhmon SSH inject failed for location {location.id}: {e}")
        return False, str(e)

"""
mikhmon_config.py
Injects a location into Mikhmon V3 config.php on the VPS host.

Mikhmon V3 runs at /root/mikhmon-v3/ via: php -S 0.0.0.0:8081
Config: /root/mikhmon-v3/include/config.php

readcfg.php reads array by numeric keys 1-11:
  [1]  ip           explode('!', ...)[1]
  [2]  api_user     explode('@|@', ...)[1]
  [3]  api_pass     explode('#|#', ...)[1]
  [4]  hotspot_name explode('%', ...)[1]
  [5]  dns          explode('^', ...)[1]
  [6]  currency     explode('&', ...)[1]
  [7]  auto_reload  explode('*', ...)[1]
  [8]  iface        explode('(', ...)[1]
  [9]  infolp       explode(')', ...)[1]
  [10] idle_timeout explode('=', ...)[1]
  [11] live_report  explode('@!@', ...)[1]
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

CONFIG_PATH = '/root/mikhmon-v3/include/config.php'


def inject_mikhmon_session(location):
    """
    SSH into VPS and inject location into Mikhmon V3 config.php.
    Returns (True, None) on success or (False, error_str) on failure.
    """
    try:
        import paramiko
    except ImportError:
        return False, "paramiko not installed"

    host     = getattr(settings, 'VPS_SSH_HOST', '')
    user     = getattr(settings, 'VPS_SSH_USER', 'root')
    password = getattr(settings, 'VPS_SSH_PASS', '')
    config_path = getattr(settings, 'MIKHMON_CONFIG_PATH', '/root/mikhmon-v3/include/config.php')

    if not host or not password:
        return False, "VPS SSH credentials not configured"

    session_key  = location.location_slug.upper().replace('-', '_')
    vpn_subnet   = getattr(settings, 'VPN_SUBNET', '10.8.0')
    vpn_ip       = getattr(location, '_ovpn_ip_override', None) or "{}.{}".format(vpn_subnet, location.id + 1)
    api_user     = location.vpn_api_user
    api_pass     = location.vpn_api_password
    hotspot_name = location.site_name
    dns_name     = location.hotspot_dns or 'hot.spot'

    # Keys 1-11 match readcfg.php numeric index reads exactly
    new_entry = (
        "$data['{k}'] = array ("
        "'1'=>'{k}!{ip}',"
        "'2'=>'{k}@|@{u}',"
        "'3'=>'{k}#|#{p}',"
        "'4'=>'{k}%{name}',"
        "'5'=>'{k}^{dns}',"
        "'6'=>'{k}&UGX',"
        "'7'=>'{k}*10',"
        "'8'=>'{k}(1',"
        "'9'=>'{k})',"
        "'10'=>'{k}=10',"
        "'11'=>'{k}@!@disable');"
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

        out, err = run("cat '{}'".format(config_path))
        if not out:
            client.close()
            return False, "Could not read V3 config at {}".format(config_path)

        content = out
        import re

        # Already injected — update entry completely with latest credentials
        if "$data['{}']".format(session_key) in content:
            pattern = r"\$data\['" + re.escape(session_key) + r"'\] = array \([^;]+;\n?"
            updated = re.sub(pattern, new_entry + "\n", content)
            sftp = client.open_sftp()
            with sftp.open(config_path, 'w') as f:
                f.write(updated)
            sftp.close()
            logger.info("Mikhmon V3 session '{}' updated for location {}".format(session_key, location.id))
            client.close()
            location.mikhmon_session = session_key
            location.save(update_fields=['mikhmon_session'])
            return True, None

        # Insert before $data['mikhmon'] auth line which is always last
        if "$data['mikhmon']" in content:
            updated = content.replace("$data['mikhmon']", new_entry + "\n$data['mikhmon']", 1)
        else:
            updated = content.rstrip() + "\n" + new_entry + "\n"

        sftp = client.open_sftp()
        with sftp.open(config_path, 'w') as f:
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

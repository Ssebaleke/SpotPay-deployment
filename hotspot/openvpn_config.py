"""
openvpn_config.py
Generates OpenVPN client cert and config for ROS v6 MikroTik locations.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_ovpn_config(location):
    """
    Generates an OpenVPN client cert on the VPS for this location.
    Stores the .ovpn config in location.ovpn_client_config.
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

    client_name = f"spotpay_loc{location.id}"
    # Assign static IP from 10.9.0.X subnet (starting at .2)
    client_ip = f"10.9.0.{location.id + 1}"

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, password=password, timeout=15)

        def run(cmd, timeout=30):
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            return out, err

        # Check if cert already exists
        out, _ = run(f'ls /etc/openvpn/easy-rsa/pki/issued/{client_name}.crt 2>/dev/null')
        if client_name not in out:
            # Generate request
            run(f'cd /etc/openvpn/easy-rsa && ./easyrsa gen-req {client_name} nopass', timeout=60)
            # Sign it
            out, err = run(f'cd /etc/openvpn/easy-rsa && echo "yes" | ./easyrsa sign-req client {client_name}', timeout=60)
            if 'Certificate created' not in out and 'Certificate created' not in err:
                client.close()
                return False, f"Cert signing failed: {err}"

        # Assign static IP
        run(f'echo "ifconfig-push {client_ip} 255.255.255.0" > /etc/openvpn/ccd/{client_name}')

        # Read certs
        ca, _   = run('cat /etc/openvpn/ca.crt')
        cert, _ = run(f'cat /etc/openvpn/easy-rsa/pki/issued/{client_name}.crt')
        key, _  = run(f'cat /etc/openvpn/easy-rsa/pki/private/{client_name}.key')
        ta, _   = run('cat /etc/openvpn/ta.key')
        client.close()

        if not ca or not cert or not key:
            return False, "Failed to read cert files"

        # Build .ovpn config
        vps_ip = getattr(settings, 'VPS_SSH_HOST', host)
        ovpn = (
            f"client\n"
            f"dev tun\n"
            f"proto tcp\n"
            f"remote {vps_ip} 1194\n"
            f"resolv-retry infinite\n"
            f"nobind\n"
            f"persist-key\n"
            f"persist-tun\n"
            f"cipher AES-256-CBC\n"
            f"auth SHA1\n"
            f"verb 3\n"
            f"<ca>\n{ca}\n</ca>\n"
            f"<cert>\n{cert}\n</cert>\n"
            f"<key>\n{key}\n</key>\n"
        )

        location.ovpn_client_config = ovpn
        location.save(update_fields=['ovpn_client_config'])

        logger.info(f"OpenVPN config generated for location {location.id} — IP {client_ip}")
        return True, client_ip

    except Exception as e:
        logger.error(f"OpenVPN config generation failed for location {location.id}: {e}")
        return False, str(e)

import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=30)

def run(cmd, timeout=180):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

# Check what already exists
print("=== Checking existing certs ===")
out, _ = run('ls /etc/openvpn/easy-rsa/pki/issued/ 2>/dev/null')
print("Issued:", out)
out, _ = run('ls /etc/openvpn/easy-rsa/pki/private/ 2>/dev/null')
print("Private:", out)
out, _ = run('ls /etc/openvpn/dh.pem /etc/openvpn/ta.key 2>/dev/null')
print("DH/TA:", out)

# Generate server cert if missing
if 'server.crt' not in run('ls /etc/openvpn/easy-rsa/pki/issued/ 2>/dev/null')[0]:
    print("\n=== Generating server cert ===")
    out, err = run('cd /etc/openvpn/easy-rsa && ./easyrsa build-server-full server nopass', timeout=120)
    print(out[-300:] or err[-300:])
else:
    print("Server cert already exists")

# Generate DH if missing
if 'dh.pem' not in run('ls /etc/openvpn/easy-rsa/pki/ 2>/dev/null')[0]:
    print("\n=== Generating DH params (takes ~1 min) ===")
    out, err = run('cd /etc/openvpn/easy-rsa && ./easyrsa gen-dh', timeout=180)
    print(out[-200:] or err[-200:])
else:
    print("DH already exists")

# Generate TA key if missing
if 'ta.key' not in run('ls /etc/openvpn/ 2>/dev/null')[0]:
    print("\n=== Generating TLS auth key ===")
    run('openvpn --genkey secret /etc/openvpn/ta.key')
    print("TA key generated")
else:
    print("TA key already exists")

# Copy certs
print("\n=== Copying certs ===")
run('cp /etc/openvpn/easy-rsa/pki/ca.crt /etc/openvpn/')
run('cp /etc/openvpn/easy-rsa/pki/issued/server.crt /etc/openvpn/')
run('cp /etc/openvpn/easy-rsa/pki/private/server.key /etc/openvpn/')
run('cp /etc/openvpn/easy-rsa/pki/dh.pem /etc/openvpn/')
print("Done")

# Write server config
server_conf = """port 1194
proto tcp
dev tun
ca /etc/openvpn/ca.crt
cert /etc/openvpn/server.crt
key /etc/openvpn/server.key
dh /etc/openvpn/dh.pem
tls-auth /etc/openvpn/ta.key 0
server 10.9.0.0 255.255.255.0
ifconfig-pool-persist /var/log/openvpn/ipp.txt
keepalive 10 120
cipher AES-256-CBC
persist-key
persist-tun
status /var/log/openvpn/openvpn-status.log
client-config-dir /etc/openvpn/ccd
verb 3
"""
run('mkdir -p /var/log/openvpn /etc/openvpn/ccd /etc/openvpn/clients')
sftp = client.open_sftp()
with sftp.open('/etc/openvpn/server.conf', 'w') as f:
    f.write(server_conf)
sftp.close()
print("Server config written")

# Enable IP forwarding
run("sysctl -w net.ipv4.ip_forward=1")
run("grep -q 'net.ipv4.ip_forward=1' /etc/sysctl.conf || echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf")

# Start OpenVPN
print("\n=== Starting OpenVPN ===")
out, err = run('systemctl enable openvpn@server && systemctl restart openvpn@server', timeout=30)
print(out or err or "started")

import time
time.sleep(3)
out, _ = run('systemctl is-active openvpn@server')
print("Status:", out)

out, _ = run('ip addr show tun0 2>/dev/null | grep inet || echo "tun0 not up"')
print("tun0:", out)

client.close()
print("\nDone.")

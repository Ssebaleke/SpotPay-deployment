import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=30)

def run(cmd, timeout=120):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

print("=== Installing OpenVPN and Easy-RSA ===")
out, err = run('apt-get install -y openvpn easy-rsa', timeout=180)
print(out[-500:] or err[-500:])

print("\n=== Setting up PKI ===")
run('mkdir -p /etc/openvpn/easy-rsa')
run('cp -r /usr/share/easy-rsa/* /etc/openvpn/easy-rsa/')
run('cd /etc/openvpn/easy-rsa && ./easyrsa init-pki', timeout=30)

print("\n=== Building CA (no passphrase) ===")
out, err = run('cd /etc/openvpn/easy-rsa && echo "SpotPay-CA" | ./easyrsa build-ca nopass', timeout=60)
print(out[-300:] or err[-300:])

print("\n=== Generating server cert ===")
out, err = run('cd /etc/openvpn/easy-rsa && ./easyrsa build-server-full server nopass', timeout=60)
print(out[-300:] or err[-300:])

print("\n=== Generating DH params ===")
out, err = run('cd /etc/openvpn/easy-rsa && ./easyrsa gen-dh', timeout=120)
print(out[-200:] or err[-200:])

print("\n=== Generating TLS auth key ===")
out, err = run('openvpn --genkey secret /etc/openvpn/ta.key')
print(out or err or "done")

print("\n=== Copying certs to /etc/openvpn ===")
run('cp /etc/openvpn/easy-rsa/pki/ca.crt /etc/openvpn/')
run('cp /etc/openvpn/easy-rsa/pki/issued/server.crt /etc/openvpn/')
run('cp /etc/openvpn/easy-rsa/pki/private/server.key /etc/openvpn/')
run('cp /etc/openvpn/easy-rsa/pki/dh.pem /etc/openvpn/')
print("Certs copied")

print("\n=== Creating OpenVPN server config ===")
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
push "route 10.9.0.0 255.255.255.0"
keepalive 10 120
cipher AES-256-CBC
persist-key
persist-tun
status /var/log/openvpn/openvpn-status.log
verb 3
client-config-dir /etc/openvpn/ccd
"""
run('mkdir -p /var/log/openvpn /etc/openvpn/ccd /etc/openvpn/clients')

sftp = client.open_sftp()
with sftp.open('/etc/openvpn/server.conf', 'w') as f:
    f.write(server_conf)
sftp.close()
print("Server config written")

print("\n=== Enabling IP forwarding ===")
run("echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf")
run("sysctl -p")

print("\n=== Starting OpenVPN ===")
out, err = run('systemctl enable openvpn@server && systemctl start openvpn@server', timeout=30)
print(out or err or "started")

out, err = run('systemctl is-active openvpn@server')
print("OpenVPN status:", out)

print("\n=== Checking tun0 interface ===")
out, err = run('ip addr show tun0 2>/dev/null || echo "tun0 not up yet"')
print(out)

client.close()
print("\nDone.")

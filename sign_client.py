import paramiko, warnings, time
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=30)

def run(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

client_name = 'spotpay_loc4'

# Sign the existing request
print("=== Signing client cert request ===")
out, err = run(f'cd /etc/openvpn/easy-rsa && echo "yes" | ./easyrsa sign-req client {client_name}', timeout=60)
print(out[-300:] or err[-300:])

# Verify
out, _ = run(f'ls /etc/openvpn/easy-rsa/pki/issued/{client_name}.crt 2>/dev/null')
print("Cert exists:", out)

# Read certs
ca, _ = run('cat /etc/openvpn/ca.crt')
cert, _ = run(f'cat /etc/openvpn/easy-rsa/pki/issued/{client_name}.crt')
key, _ = run(f'cat /etc/openvpn/easy-rsa/pki/private/{client_name}.key')
ta, _ = run('cat /etc/openvpn/ta.key')

ovpn = f"""client
dev tun
proto tcp
remote 68.168.222.37 1194
resolv-retry infinite
nobind
persist-key
persist-tun
cipher AES-256-CBC
verb 3
key-direction 1
<ca>
{ca}
</ca>
<cert>
{cert}
</cert>
<key>
{key}
</key>
<tls-auth>
{ta}
</tls-auth>
"""

with open('test_client.ovpn', 'w', encoding='utf-8') as f:
    f.write(ovpn)
print(f"Client config written ({len(ovpn)} chars)")

# Assign static IP
run(f'echo "ifconfig-push 10.9.0.5 255.255.255.0" > /etc/openvpn/ccd/{client_name}')
print("Static IP: 10.9.0.5")

client.close()
print("Done.")

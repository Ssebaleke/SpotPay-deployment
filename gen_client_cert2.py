import paramiko, warnings, time
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=30)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

client_name = 'spotpay_loc4'

# Check if already exists
out, _ = run(f'ls /etc/openvpn/easy-rsa/pki/issued/{client_name}.crt 2>/dev/null')
if client_name in out:
    print("Client cert already exists")
else:
    # Run in background
    print("Generating client cert in background...")
    run(f'nohup bash -c "cd /etc/openvpn/easy-rsa && ./easyrsa build-client-full {client_name} nopass > /tmp/easyrsa_log.txt 2>&1" &')
    
    # Wait up to 3 minutes
    for i in range(18):
        time.sleep(10)
        out, _ = run(f'ls /etc/openvpn/easy-rsa/pki/issued/{client_name}.crt 2>/dev/null')
        if client_name in out:
            print(f"Done after {(i+1)*10}s")
            break
        print(f"Waiting... {(i+1)*10}s")
    else:
        log, _ = run('cat /tmp/easyrsa_log.txt')
        print("Log:", log)

# Now read certs and build ovpn
out, _ = run(f'ls /etc/openvpn/easy-rsa/pki/issued/{client_name}.crt 2>/dev/null')
if client_name not in out:
    print("Cert still not ready")
    client.close()
    exit()

print("Reading certs...")
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
print("Client config written to test_client.ovpn")

# Assign static IP
run(f'echo "ifconfig-push 10.9.0.5 255.255.255.0" > /etc/openvpn/ccd/{client_name}')
print("Static IP assigned: 10.9.0.5")

client.close()
print("Done.")

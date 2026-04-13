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

# Sign the server cert request
print("=== Signing server cert ===")
out, err = run('cd /etc/openvpn/easy-rsa && echo "yes" | ./easyrsa sign-req server server', timeout=60)
print(out[-300:] or err[-300:])

# Copy signed cert
run('cp /etc/openvpn/easy-rsa/pki/issued/server.crt /etc/openvpn/')
print("Server cert copied")

# Start OpenVPN
print("\n=== Starting OpenVPN ===")
run('systemctl enable openvpn@server && systemctl restart openvpn@server', timeout=30)
time.sleep(3)

out, _ = run('systemctl is-active openvpn@server')
print("Status:", out)

out, _ = run('ip addr show tun0 2>/dev/null | grep inet || echo "tun0 not up"')
print("tun0:", out)

out, _ = run('journalctl -u openvpn@server --no-pager -n 10 2>/dev/null')
with open('openvpn_log.txt', 'w', encoding='utf-8', errors='replace') as f:
    f.write(out)
print("Logs written to openvpn_log.txt")

client.close()
print("Done.")

import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print("=== Running services ===")
print(run('ss -tlnp | grep -E "1194|1723|443|8443|1701"'))

print("\n=== Installed VPN packages ===")
print(run('which openvpn sstp-client xl2tpd pptpd 2>/dev/null || echo "none found"'))
print(run('dpkg -l | grep -E "openvpn|sstp|l2tp|pptpd" 2>/dev/null || echo "none"'))

print("\n=== WireGuard config ===")
print(run('cat /etc/wireguard/wg0.conf 2>/dev/null || echo "no wg0.conf"'))

print("\n=== WireGuard peers count ===")
print(run('wg show wg0 peers 2>/dev/null | wc -l'))

print("\n=== OS version ===")
print(run('cat /etc/os-release | grep PRETTY'))

client.close()

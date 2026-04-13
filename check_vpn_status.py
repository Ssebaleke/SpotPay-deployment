import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print("=== WireGuard peers ===")
print(run('wg show wg0'))

print("\n=== Mikhmon config ===")
print(run('cat /root/mikhmon-v3/include/config.php'))

print("\n=== Test API connection to location 4 VPN IP ===")
print(run('ping -c 3 -W 2 10.8.0.5 2>/dev/null || echo "unreachable"'))

print("\n=== Test API port 8728 on location 4 ===")
print(run('nc -zv 10.8.0.5 8728 2>&1 || echo "port closed"'))

client.close()

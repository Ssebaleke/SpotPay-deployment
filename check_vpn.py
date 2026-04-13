import paramiko
import warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

# 1. Check WireGuard peers
print("=== WireGuard Peers ===")
out, err = run('wg show wg0')
print(out or err)

# 2. Check Mikhmon config.php
print("\n=== Mikhmon config.php ===")
out, err = run('cat /root/mikhmon-v3/include/config/config.php')
print(out or err)

# 3. Check web logs for register-vpn
print("\n=== register-vpn logs ===")
out, err = run('docker logs spotpay-deployment-web-1 --tail 50 2>&1 | grep -i "register\|vpn\|mikhmon\|spotpay_8x58i6"')
print(out or "nothing found")

client.close()

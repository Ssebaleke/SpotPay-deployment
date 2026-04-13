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

# Find Mikhmon config
print("=== Finding Mikhmon config ===")
out, err = run('find / -name "config.php" 2>/dev/null | grep -i mikhmon')
print(out or "not found")

# Check mikhmon container
print("\n=== Mikhmon container ===")
out, err = run('docker inspect mikhmon-app | grep -i mount')
print(out or err)

# Check mikhmon volumes
print("\n=== Mikhmon volumes ===")
out, err = run('docker inspect mikhmon-app --format "{{json .Mounts}}"')
print(out or err)

# Check register-vpn was called
print("\n=== Full recent logs ===")
out, err = run('docker logs spotpay-deployment-web-1 --tail 20 2>&1')
print(out or err)

client.close()

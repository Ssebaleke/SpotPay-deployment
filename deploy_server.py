import paramiko
import warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

PROJECT = '/root/SpotPay-deployment'

# New variables to add
new_vars = """
# Mikhmon
MIKHMON_URL=http://68.168.222.37:8081
MIKHMON_USER=mikhmon
MIKHMON_PASS=1234

# WireGuard VPN
VPN_SERVER_IP=68.168.222.37
VPN_SERVER_PORT=443
VPN_SERVER_PUBLIC_KEY=A+DWtxhzShYGxd/2hgRqFSeutH+ixJ69jG+APXSlXR4=
VPN_INTERFACE_NAME=wg0
VPN_SUBNET=10.8.0

# VPS SSH (for Mikhmon auto-config)
VPS_SSH_HOST=68.168.222.37
VPS_SSH_USER=root
VPS_SSH_PASS=Vico@2026
MIKHMON_CONFIG_PATH=/root/mikhmon-v3/include/config/config.php
"""

# Check if already added
out, _ = run(f'cat {PROJECT}/.env')
if 'MIKHMON_URL' in out:
    print("Variables already in .env — skipping append")
else:
    # Append via SFTP
    sftp = client.open_sftp()
    with sftp.open(f'{PROJECT}/.env', 'a') as f:
        f.write(new_vars)
    sftp.close()
    print("New variables appended to .env")

# Pull latest code
print("\nPulling latest code...")
out, err = run(f'cd {PROJECT} && git pull origin main')
print(out)
if err:
    print("ERR:", err)

# Rebuild Docker
print("\nRebuilding Docker containers...")
out, err = run(f'cd {PROJECT} && docker-compose down && docker-compose up -d --build 2>&1')
print(out[:3000])
if err:
    print("ERR:", err[:1000])

client.close()
print("\nDone.")

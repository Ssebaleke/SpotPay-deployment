import paramiko, warnings, sys
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd):
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out or err

print('=== STARTING CONTAINERS ===')
print(run('cd /root/SpotPay-deployment && docker compose up -d --build 2>&1'))

print('\n=== CONTAINERS STATUS ===')
print(run('docker ps -a'))

client.close()

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

# Find .env files
out, err = run('find /root/SpotPay-deployment -name ".env" 2>/dev/null')
print(".env files:", out)

# Find docker-compose
out, err = run('find /root/SpotPay-deployment -name "docker-compose.yml" 2>/dev/null')
print("docker-compose:", out)

# List SpotPay-deployment
out, err = run('ls /root/SpotPay-deployment/')
print("project root:", out)

client.close()

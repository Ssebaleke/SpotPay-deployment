import paramiko
import warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=120):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

PROJECT = '/root/SpotPay-deployment'

# Check docker version
out, err = run('docker compose version || docker-compose version')
print("Docker:", out or err)

# Rebuild
print("\nRebuilding...")
out, err = run(f'cd {PROJECT} && docker compose down && docker compose up -d --build', timeout=300)
print(out[:3000])
if err:
    print("ERR:", err[:1000])

# Check running containers
out, err = run('docker ps')
print("\nRunning containers:\n", out)

client.close()
print("\nDone.")

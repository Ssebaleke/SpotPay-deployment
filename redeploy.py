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

out, err = run(f'cd {PROJECT} && git pull origin main')
print("Pull:", out)

out, err = run(f'cd {PROJECT} && docker compose up -d --build', timeout=300)
print("Build:", err[:500] if err else out[:500])

out, err = run('docker ps --format "table {{.Names}}\t{{.Status}}"')
print("\nContainers:\n", out)

client.close()
print("Done.")

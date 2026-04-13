import paramiko, warnings
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

# Kill everything
run('docker rm -f spotpay-deployment-redis-1 spotpay-deployment-web-1 spotpay-deployment-scheduler-1 spotpay-deployment-nginx-1 2>/dev/null || true')
run('docker network rm spotpay-deployment_default 2>/dev/null || true')

# Start fresh
out, err = run(f'cd {PROJECT} && docker compose up -d', timeout=120)
print(err[:500] if err else out[:500])

out, _ = run('docker ps --format "table {{.Names}}\t{{.Status}}"')
print("\nContainers:\n", out)

client.close()

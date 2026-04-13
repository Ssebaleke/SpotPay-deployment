import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

PROJECT = '/root/SpotPay-deployment'

# Update MIKHMON_URL to use new domain
run(f"sed -i 's|MIKHMON_URL=.*|MIKHMON_URL=https://mikhmon.spotpay.it.com|' {PROJECT}/.env")
out, _ = run(f"grep MIKHMON_URL {PROJECT}/.env")
print("Updated MIKHMON_URL:", out)

# Pull latest code
out, err = run(f'cd {PROJECT} && git pull origin main')
print("Pull:", out)

# Get SSL cert for mikhmon subdomain (stop nginx first to free port 80/443)
print("\nGetting SSL cert for mikhmon.spotpay.it.com...")
run(f'cd {PROJECT} && docker compose down || true', timeout=30)
out, err = run(
    'certbot certonly --standalone -d mikhmon.spotpay.it.com '
    '--non-interactive --agree-tos --email support@spotpay.it.com',
    timeout=60
)
print("Certbot:", out or err)

# Copy certs
run(f'mkdir -p {PROJECT}/ssl')
run(f'cp /etc/letsencrypt/live/mikhmon.spotpay.it.com/fullchain.pem {PROJECT}/ssl/mikhmon_fullchain.pem')
run(f'cp /etc/letsencrypt/live/mikhmon.spotpay.it.com/privkey.pem {PROJECT}/ssl/mikhmon_privkey.pem')
print("Certs copied")

# Restart
out, err = run(f'cd {PROJECT} && docker compose up -d --build', timeout=300)
print("Restart:", err[:500] if err else out[:500])

out, _ = run('docker ps --format "table {{.Names}}\t{{.Status}}"')
print("\nContainers:\n", out)

client.close()
print("Done.")

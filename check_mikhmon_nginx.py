import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print("=== Nginx config for mikhmon ===")
print(run('grep -A5 "mikhmon" /root/SpotPay-deployment/nginx.conf'))

print("\n=== Nginx container mikhmon logs ===")
print(run('docker logs spotpay-deployment-nginx-1 --tail 10 2>&1 | grep -i mikhmon || echo "no mikhmon logs"'))

print("\n=== Test mikhmon subdomain from server ===")
print(run('curl -sk -o /dev/null -w "%{http_code}" https://mikhmon.spotpay.it.com/admin.php?id=login --max-time 5'))

print("\n=== SSL cert for mikhmon ===")
print(run('ls /root/SpotPay-deployment/ssl/ | grep mikhmon'))

client.close()

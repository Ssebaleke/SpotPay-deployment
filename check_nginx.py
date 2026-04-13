import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=20):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

print("=== Nginx logs ===")
print(run('docker logs spotpay-deployment-nginx-1 --tail 20 2>&1')[0])

print("\n=== Nginx config test ===")
print(run('docker exec spotpay-deployment-nginx-1 nginx -t 2>&1')[1])

print("\n=== SSL certs ===")
print(run('ls /root/SpotPay-deployment/ssl/')[0])

client.close()

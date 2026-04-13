import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print("=== Nginx error logs ===")
print(run('docker logs spotpay-deployment-nginx-1 --tail 20 2>&1 | grep -i "mikhmon\|502\|error\|connect"'))

print("\n=== 172.17.0.1 reachable from nginx container ===")
print(run('docker exec spotpay-deployment-nginx-1 wget -q -O- --timeout=3 http://172.17.0.1:8081/admin.php?id=login 2>&1 | head -5 || echo "failed"'))

print("\n=== PHP process still running ===")
print(run('ps aux | grep "php -S 0.0.0.0:8081" | grep -v grep'))

client.close()

import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print("Mikhmon container:", run('docker ps | grep mikhmon'))
print("Port 8080:", run('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/'))
print("Port 8081:", run('curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/'))
print("Mikhmon env:", run('grep MIKHMON /root/SpotPay-deployment/.env'))
print("Recent 500s:", run('docker logs spotpay-deployment-web-1 --tail 30 2>&1 | grep -i "500\|error\|mikhmon"'))

client.close()

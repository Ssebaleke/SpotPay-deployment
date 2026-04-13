import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

# Find the correct gateway IP from inside nginx container
print("=== Gateway IP from nginx container ===")
print(run('docker exec spotpay-deployment-nginx-1 ip route | grep default'))

print("\n=== Host IP from nginx container ===")
print(run('docker exec spotpay-deployment-nginx-1 cat /etc/hosts | grep host'))

# Try different IPs
for ip in ['172.17.0.1', '172.18.0.1', '10.0.0.1']:
    result = run(f'docker exec spotpay-deployment-nginx-1 nc -zw2 {ip} 8081 2>&1 && echo "OPEN" || echo "CLOSED"')
    print(f"{ip}:8081 -> {result}")

client.close()

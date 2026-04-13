import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print("=== Port 8081 listening ===")
print(run('ss -tlnp | grep 8081'))

print("\n=== PHP process ===")
print(run('ps aux | grep "php -S" | grep -v grep'))

print("\n=== Test port 8081 ===")
print(run('curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/'))

print("\n=== Nginx mikhmon proxy ===")
print(run('curl -s -o /dev/null -w "%{http_code}" https://mikhmon.spotpay.it.com/'))

client.close()

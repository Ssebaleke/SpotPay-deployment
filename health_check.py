import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print("=== Running containers ===")
print(run('docker ps --format "table {{.Names}}\t{{.Status}}"'))

print("\n=== Recent billing/payment logs ===")
out = run('docker logs spotpay-deployment-web-1 --tail 20 2>&1')
with open('billing_check.txt', 'w', encoding='utf-8', errors='replace') as f:
    f.write(out)
print("Written to billing_check.txt")

print("\n=== Mikhmon V3 status ===")
print(run('curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/'))

print("\n=== Mikhmon config ===")
print(run('cat /root/mikhmon-v3/include/config.php'))

print("\n=== WireGuard peers ===")
print(run('wg show wg0 | grep -E "peer|allowed|handshake"'))

client.close()

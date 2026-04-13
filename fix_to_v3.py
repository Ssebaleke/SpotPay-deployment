import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

PROJECT = '/root/SpotPay-deployment'

# Fix port back to 8081 (Mikhmon V3) and fix config path
run(f"sed -i 's|MIKHMON_URL=.*|MIKHMON_URL=http://68.168.222.37:8081|' {PROJECT}/.env")
run(f"sed -i 's|MIKHMON_CONFIG_PATH=.*|MIKHMON_CONFIG_PATH=/root/mikhmon-v3/include/config.php|' {PROJECT}/.env")

print("Updated env:")
print(run(f'grep -E "MIKHMON" {PROJECT}/.env'))

# Check Mikhmon V3 config
print("\n=== Mikhmon V3 config.php ===")
print(run('cat /root/mikhmon-v3/include/config.php'))

# Test V3 URL
print("\n=== Test V3 login URL ===")
print(run('curl -s -o /dev/null -w "%{http_code}" "http://localhost:8081/index.php?admin&login&user=mikhmon&pass=1234"'))

# Restart web container
run(f'cd {PROJECT} && docker compose restart web')
print("\nWeb container restarted.")

client.close()

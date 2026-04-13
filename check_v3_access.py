import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

# Check firewall/iptables for port 8081
print("=== Firewall rules for 8081 ===")
print(run('iptables -L INPUT -n | grep 8081 || echo "no rule"'))
print(run('ufw status 2>/dev/null | grep 8081 || echo "ufw not active or no rule"'))

# Check if 8081 is accessible from outside
print("\n=== Port 8081 listening ===")
print(run('ss -tlnp | grep 8081'))

# Check Mikhmon V3 index.php for the correct bypass format
print("\n=== Mikhmon V3 index.php login logic ===")
print(run('grep -n "admin\|login\|session\|pass" /root/mikhmon-v3/index.php | head -30'))

# Check admin.php
print("\n=== admin.php login check ===")
print(run('grep -n "admin\|login\|session\|pass\|user" /root/mikhmon-v3/admin.php | head -30'))

client.close()

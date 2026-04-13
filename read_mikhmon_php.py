import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

# Read full index.php login section
print("=== index.php lines 1-50 ===")
print(run('head -50 /root/mikhmon-v3/index.php'))

print("\n=== admin.php lines 60-100 ===")
print(run('sed -n "60,100p" /root/mikhmon-v3/admin.php'))

client.close()

import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip(), stderr.read().decode('utf-8', errors='ignore').strip()

# Read the full raw config
out, err = run("docker exec mikhmon-app cat /var/www/html/config/config.php")
print("RAW CONFIG:")
print(repr(out[:500]))

client.close()

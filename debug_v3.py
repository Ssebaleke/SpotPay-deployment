import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

# Follow redirects and get final response
print("=== Following redirect ===")
print(run('curl -sL -o /dev/null -w "%{http_code} %{url_effective}" "http://localhost:8081/index.php?admin&login&user=mikhmon&pass=1234&session=VICOTECH_FASTNET"'))

# Get actual response body
print("\n=== Response body ===")
print(run('curl -sL "http://localhost:8081/index.php?admin&login&user=mikhmon&pass=1234&session=VICOTECH_FASTNET" | head -50'))

# Check Mikhmon V3 error logs
print("\n=== PHP error log ===")
print(run('tail -20 /root/mikhmon-v3/mikhmon_log.txt 2>/dev/null || echo "no log"'))

# Check if PHP is running
print("\n=== PHP process ===")
print(run('ps aux | grep php | grep -v grep'))

client.close()

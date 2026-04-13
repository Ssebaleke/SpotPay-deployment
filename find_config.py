import paramiko
import warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=20):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

# Find config.php inside container
out, err = run("docker exec mikhmon-app find / -name 'config.php' 2>/dev/null")
print("All config.php files in container:\n", out or err)

# Check web logs for Mikhmon injection result
out, err = run("docker logs spotpay-deployment-web-1 --tail 30 2>&1")
# Write to file to avoid encoding issues
with open('web_logs.txt', 'w', encoding='utf-8', errors='replace') as f:
    f.write(out)
print("Logs written to web_logs.txt")

client.close()

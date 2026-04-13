import paramiko
import warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

PROJECT = '/root/SpotPay-deployment'

# Fix the config path in .env
out, err = run(f"sed -i 's|MIKHMON_CONFIG_PATH=.*|MIKHMON_CONFIG_PATH=/root/mikhmon-v3/include/config.php|' {PROJECT}/.env")
print("Fixed config path:", out or "done")

# Verify
out, err = run(f"grep MIKHMON_CONFIG_PATH {PROJECT}/.env")
print("Current value:", out)

# Restart web container to pick up new env
out, err = run(f"cd {PROJECT} && docker compose restart web", timeout=30)
print("Restart:", out or err)

client.close()
print("Done.")

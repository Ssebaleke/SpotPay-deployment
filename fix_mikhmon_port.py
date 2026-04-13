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

# Fix port 8081 -> 8080
out, err = run(f"sed -i 's|MIKHMON_URL=http://68.168.222.37:8081|MIKHMON_URL=http://68.168.222.37:8080|' {PROJECT}/.env")
print("Fixed:", out or "done")

# Verify
out, err = run(f"grep MIKHMON_URL {PROJECT}/.env")
print("Current:", out)

# Restart web to pick up new env
out, err = run(f"cd {PROJECT} && docker compose restart web", timeout=30)
print("Restart:", err or out)

client.close()
print("Done.")

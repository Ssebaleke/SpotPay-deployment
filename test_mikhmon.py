import paramiko
import warnings
import requests
warnings.filterwarnings('ignore')

# Test the register-vpn endpoint directly
print("=== Testing register-vpn endpoint ===")
resp = requests.post(
    'https://spotpay.it.com/api/register-vpn/',
    data={
        'location_id': '4',
        'public_key': 'rcOsQT8Qe0R/BnuSzdy6UREG6Gw3eEKs/adp8KPY5QQ='
    },
    timeout=30
)
print("Status:", resp.status_code)
print("Response:", resp.text)

# Check Mikhmon config after
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    return out

print("\n=== Mikhmon config.php (inside container) ===")
out = run("docker exec mikhmon-app find / -name 'config.php' 2>/dev/null | grep -i mikhmon | head -1")
print("Config path:", out)
if out:
    content = run(f"docker exec mikhmon-app cat '{out}'")
    print("Content:", content[:2000])

client.close()

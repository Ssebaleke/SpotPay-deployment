import paramiko, warnings, requests
warnings.filterwarnings('ignore')

# Test 1: Check what SpotPay redirects to
print("=== Test 1: SpotPay redirect for location 4 ===")
try:
    resp = requests.get(
        'https://spotpay.it.com/locations/voucher-generator/4/open/',
        allow_redirects=False,
        timeout=10,
    )
    print("Status:", resp.status_code)
    print("Location header:", resp.headers.get('Location', 'none'))
    print("Set-Cookie:", resp.headers.get('Set-Cookie', 'none'))
except Exception as e:
    print("Error:", e)

# Test 2: Check Mikhmon V3 login from server
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=20):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print("\n=== Test 2: Mikhmon V3 login POST from server ===")
print(run('''curl -si -X POST "http://localhost:8081/admin.php?id=login" \
    -d "user=mikhmon&pass=1234&login=1" | head -20'''))

# Test 3: Check Mikhmon password in config
print("\n=== Test 3: Mikhmon admin credentials ===")
print(run('grep -r "useradm\|passadm" /root/mikhmon-v3/include/ 2>/dev/null | head -10'))
print(run('cat /root/mikhmon-v3/include/config.php | head -5'))

client.close()

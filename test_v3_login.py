import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

# Step 1: POST login to get session cookie
print("=== Step 1: Login POST ===")
out = run('''curl -s -c /tmp/mikhmon_cookies.txt -b /tmp/mikhmon_cookies.txt \
    -X POST "http://localhost:8081/admin.php?id=login" \
    -d "user=mikhmon&pass=1234&login=1" \
    -o /dev/null -w "%{http_code} %{redirect_url}"''')
print("Login response:", out)

# Step 2: Check cookies
print("\n=== Cookies ===")
print(run('cat /tmp/mikhmon_cookies.txt'))

# Step 3: Access session with cookie
print("\n=== Step 3: Access session with cookie ===")
out = run('''curl -sL -c /tmp/mikhmon_cookies.txt -b /tmp/mikhmon_cookies.txt \
    "http://localhost:8081/admin.php?id=connect&session=VICOTECH_FASTNET" \
    -o /dev/null -w "%{http_code} %{url_effective}"''')
print("Session access:", out)

# Step 4: Check what the Mikhmon password is encrypted as
print("\n=== Mikhmon password encryption ===")
print(run('grep -r "decrypt\|encrypt\|passadm\|useradm" /root/mikhmon-v3/include/ | head -20'))

client.close()

import paramiko, warnings, base64
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

# Check decrypt function
print("=== decrypt function ===")
print(run('grep -A5 "function decrypt\|function encrypt" /root/mikhmon-v3/include/function.php 2>/dev/null | head -20'))

# Decode the stored password
encoded = 'aWNlbA=='
decoded = base64.b64decode(encoded).decode('utf-8')
print(f"\n=== base64 decode of aWNlbA== ===")
print(f"Decoded: {decoded}")

# Test login with decoded password
print("\n=== Test login with decoded password ===")
print(run(f'''curl -si -X POST "http://localhost:8081/admin.php?id=login" \
    -d "user=mikhmon&pass={decoded}&login=1" | grep -E "Set-Cookie|Location|302|200"'''))

# Also test with original 1234
print("\n=== Test login with 1234 ===")
print(run('''curl -si -X POST "http://localhost:8081/admin.php?id=login" \
    -d "user=mikhmon&pass=1234&login=1" | grep -E "Set-Cookie|Location|302|sessions"'''))

# Check what happens after login - does it redirect to sessions?
print("\n=== Full login response with decoded pass ===")
print(run(f'''curl -si -c /tmp/ck.txt -X POST "http://localhost:8081/admin.php?id=login" \
    -d "user=mikhmon&pass={decoded}&login=1" | grep -E "Location|sessions|login|302|200"'''))

client.close()

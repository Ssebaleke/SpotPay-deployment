import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

# All running containers
print("=== All containers ===")
print(run('docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}"'))

# All listening ports
print("\n=== Listening ports ===")
print(run('ss -tlnp | grep -E "808|809|800"'))

# Check /root for mikhmon folders
print("\n=== Mikhmon folders ===")
print(run('ls /root/ | grep -i mikhmon'))

# Check mikhmon-v3 folder
print("\n=== mikhmon-v3 contents ===")
print(run('ls /root/mikhmon-v3/ 2>/dev/null || echo "not found"'))

# Check mikhmon-vps folder
print("\n=== mikhmon-vps contents ===")
print(run('ls /root/mikhmon-vps/ 2>/dev/null || echo "not found"'))

client.close()

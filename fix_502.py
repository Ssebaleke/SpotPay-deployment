import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

# Check container status
out, _ = run('docker ps -a --format "table {{.Names}}\t{{.Status}}"')
print("Containers:\n", out)

# Check web logs
out, err = run('docker logs spotpay-deployment-web-1 --tail 50 2>&1')
with open('startup_logs.txt', 'w', encoding='utf-8', errors='replace') as f:
    f.write(out + '\n' + err)
print("\nLast logs written to startup_logs.txt")
print(out[-2000:])

client.close()

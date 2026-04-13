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

out, err = run('docker logs spotpay-deployment-web-1 --tail 50 2>&1')
with open('error_logs.txt', 'w', encoding='utf-8', errors='replace') as f:
    f.write(out + '\n' + err)
print("Written to error_logs.txt")
print(out[-2000:])

client.close()

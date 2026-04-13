import paramiko
import warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

# Find project
out, err = run('find /root /var/www /home -name "manage.py" 2>/dev/null | grep -v myvenv | grep -v ".pyc"')
print("manage.py locations:", out)

out, err = run('ls /root/')
print("root contents:", out)

client.close()

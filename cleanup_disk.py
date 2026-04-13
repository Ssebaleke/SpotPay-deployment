import paramiko, warnings, sys
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=30)

def run(cmd):
    _, stdout, stderr = client.exec_command(cmd, timeout=60)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out or err

print('=== DISK USAGE ===')
print(run('df -h'))

print('\n=== BIGGEST DIRECTORIES ===')
print(run('du -sh /var/lib/docker/* 2>/dev/null | sort -rh | head -10'))

print('\n=== DOCKER SYSTEM DF ===')
print(run('docker system df'))

print('\n--- CLEANING DOCKER ---')
print(run('docker system prune -af --volumes 2>&1'))

print('\n=== DISK AFTER CLEANUP ===')
print(run('df -h'))

client.close()
print('\nDone.')

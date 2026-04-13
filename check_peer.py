import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print("=== WireGuard peers on VPS ===")
print(run('wg show wg0'))

print("\n=== Does VPS know about kEqUdrDvQSh7rIYwzf8ZhVRkkVKCt60nCrCsE4Gunzs= ===")
print(run('wg show wg0 peers | grep kEqU || echo "NOT REGISTERED"'))

client.close()

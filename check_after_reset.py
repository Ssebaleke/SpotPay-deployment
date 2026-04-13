import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print("=== WireGuard peers ===")
print(run('wg show wg0'))

print("\n=== Recent web logs ===")
out = run('docker logs spotpay-deployment-web-1 --tail 30 2>&1')
with open('recent_logs.txt', 'w', encoding='utf-8', errors='replace') as f:
    f.write(out)
print("Written to recent_logs.txt")

print("\n=== Token files in /tmp ===")
print(run('ls /tmp/spotpay_token_* 2>/dev/null || echo "none"'))

print("\n=== Mikhmon session in DB for location 4 ===")
print(run('cd /root/SpotPay-deployment && docker compose exec -T web python manage.py shell -c "from hotspot.models import HotspotLocation; l=HotspotLocation.objects.get(id=4); print(l.mikhmon_session, l.vpn_configured, l.vpn_api_user)"'))

client.close()

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

print("\n=== Mikhmon V3 config ===")
print(run('cat /root/mikhmon-v3/include/config.php'))

print("\n=== SpotPay DB - all locations ===")
print(run('cd /root/SpotPay-deployment && docker compose exec -T web python manage.py shell -c "from hotspot.models import HotspotLocation; [print(l.id, l.site_name, l.mikhmon_session, l.vpn_api_user, l.vpn_configured) for l in HotspotLocation.objects.filter(status=\'ACTIVE\')]"'))

client.close()

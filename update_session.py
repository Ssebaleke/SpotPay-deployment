import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

PROJECT = '/root/SpotPay-deployment'

# Update mikhmon_session in DB via Django shell
cmd = f'''cd {PROJECT} && docker compose exec -T web python manage.py shell -c "
from hotspot.models import HotspotLocation
loc = HotspotLocation.objects.get(id=4)
loc.mikhmon_session = 'VICOTECH_FASTNET'
loc.save(update_fields=['mikhmon_session'])
print('Updated:', loc.site_name, '->', loc.mikhmon_session)
"'''
print(run(cmd, timeout=30))

client.close()

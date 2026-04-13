import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

config_path = '/root/mikhmon-v3/include/config.php'

# Fix VICOTECH_FASTNET — wrong credentials (admin/mZOVaWJj should be spotpay_8x58i6/8x58i6)
# Fix VICOTECH_VICOTECH_WEB — session key has double prefix, should be VICOTECH_WEB

correct_config = """<?php 
if(substr($_SERVER["REQUEST_URI"], -10) == "config.php"){header("Location:./");};
$data['VICOTECH_WEB'] = array ('1'=>'VICOTECH_WEB!10.8.0.12','VICOTECH_WEB@|@spotpay_3aec7i','VICOTECH_WEB#|#3aec7i','VICOTECH_WEB%VICOTECH-WEB','VICOTECH_WEB^vico.net','VICOTECH_WEB&UGX','VICOTECH_WEB*10','VICOTECH_WEB(1','VICOTECH_WEB)','VICOTECH_WEB=10','VICOTECH_WEB@!@disable');
$data['VICOTECH_FASTNET'] = array ('1'=>'VICOTECH_FASTNET!10.8.0.5','VICOTECH_FASTNET@|@spotpay_8x58i6','VICOTECH_FASTNET#|#8x58i6','VICOTECH_FASTNET%FastNet','VICOTECH_FASTNET^hot.spot','VICOTECH_FASTNET&UGX','VICOTECH_FASTNET*10','VICOTECH_FASTNET(1','VICOTECH_FASTNET)','VICOTECH_FASTNET=10','VICOTECH_FASTNET@!@disable');
$data['mikhmon'] = array ('1'=>'mikhmon<|<mikhmon','mikhmon>|>aWNlbA==');
"""

sftp = client.open_sftp()
with sftp.open(config_path, 'w') as f:
    f.write(correct_config)
sftp.close()

print("Config fixed. Verifying:")
print(run(f'cat {config_path}'))

# Also update SpotPay DB - fix mikhmon_session for location 11
print("\n=== Updating DB mikhmon_session for VICOTECH-WEB ===")
print(run('cd /root/SpotPay-deployment && docker compose exec -T web python manage.py shell -c "from hotspot.models import HotspotLocation; l=HotspotLocation.objects.get(id=11); l.mikhmon_session=\'VICOTECH_WEB\'; l.save(update_fields=[\'mikhmon_session\']); print(\'Updated:\', l.mikhmon_session)"'))

client.close()

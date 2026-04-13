import paramiko
import warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd):
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out or err

sections = {
    'DOCKER CONTAINERS':        'docker ps -a',
    'WIREGUARD STATUS':         'wg show',
    'WIREGUARD CONF':           'cat /etc/wireguard/wg0.conf 2>/dev/null || echo NOT FOUND',
    'SERVER ENV':               'cat /root/SpotPay-deployment/.env 2>/dev/null || echo NOT FOUND',
    'MIKHMON CONTAINER LOGS':   'docker logs mikhmon-app --tail=30 2>&1',
    'WEB CONTAINER LOGS':       'docker logs spotpay-deployment-web-1 --tail=30 2>&1',
    'NGINX CONTAINER LOGS':     'docker logs spotpay-deployment-nginx-1 --tail=15 2>&1',
    'MIKHMON CONFIG.PHP':       'docker exec mikhmon-app cat /var/www/html/config/config.php 2>/dev/null || echo NOT FOUND',
    'OPEN PORTS':               'ss -tlnp | grep -E "80|443|8081|8728|51820"',
    'DOCKER NETWORKS':          'docker network ls && docker inspect spotpay-deployment-web-1 2>/dev/null | grep -A5 Networks',
}

for title, cmd in sections.items():
    print(f'\n{"="*20} {title} {"="*20}')
    print(run(cmd))

client.close()

import warnings, sys
warnings.filterwarnings('ignore')
import paramiko

sys.stdout.reconfigure(encoding='utf-8')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', port=22, timeout=30)

def run(cmd):
    _, stdout, _ = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='ignore').strip()

print(run("""docker exec spotpay-deployment-web-1 python manage.py shell -c "
from payments.models import Payment
payments = Payment.objects.filter(purpose='TRANSACTION').order_by('-initiated_at')[:10]
for p in payments:
    print('UUID:', p.uuid)
    print('status:', p.status)
    print('phone:', p.phone)
    print('processor_msg:', p.processor_message)
    print('provider_ref:', p.provider_reference)
    print('---')
" """))

client.close()

import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

config_path = '/root/mikhmon-v3/include/config.php'

# Read current config
content = run(f'cat {config_path}')
print("Current config:\n", content)

# Build correct V3 entry for location 4 (vicotech-fastnet)
session_key = 'VICOTECH_FASTNET'
vpn_ip = '10.8.0.5'
api_user = 'spotpay_8x58i6'
api_pass = '8x58i6'
hotspot_name = 'FastNet'
dns_name = 'hot.spot'

new_entry = (
    f"$data['{session_key}'] = array ("
    f"'1'=>'{session_key}!{vpn_ip}',"
    f"'{session_key}@|@{api_user}',"
    f"'{session_key}#|#{api_pass}',"
    f"'{session_key}%{hotspot_name}',"
    f"'{session_key}^{dns_name}',"
    f"'{session_key}&UGX',"
    f"'{session_key}*10',"
    f"'{session_key}(1',"
    f"'{session_key})',"
    f"'{session_key}=10',"
    f"'{session_key}@!@disable');"
)

if session_key in content:
    print(f"\n{session_key} already exists in config")
else:
    # Inject after }; 
    updated = content.replace('};', f'}};\n{new_entry}', 1)
    
    sftp = client.open_sftp()
    with sftp.open('/tmp/v3_config.php', 'w') as f:
        f.write(updated)
    sftp.close()
    
    run(f'cp /tmp/v3_config.php {config_path}')
    print("Injected successfully")

# Verify
print("\nUpdated config:\n", run(f'cat {config_path}'))

# Test bypass URL
print("\nTest URL (302=redirect to session, 200=login page):")
print(run(f'curl -s -o /dev/null -w "%{{http_code}}" "http://localhost:8081/index.php?admin&login&user=mikhmon&pass=1234&session={session_key}"'))

client.close()

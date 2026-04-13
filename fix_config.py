import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore'), stderr.read().decode('utf-8', errors='ignore').strip()

# Read full raw config
out, err = run("docker exec mikhmon-app cat /var/www/html/config/config.php")
print("Original length:", len(out))

# The correct fixed config — restore proper structure
# Remove the broken injection and put $m_session AFTER the }; block
fixed = """<?php if(substr($_SERVER["REQUEST_URI"], -10) == "config.php"){header("Location:./");};
$m_session['vicotech-fastnet'] = 'vicotech-fastnet<|<10.8.0.5<|<spotpay_8x58i6<|<8x58i6<|<FastNet<|<hot.spot<|<no';
$data['mikhmon'] = array ('1'=>'mikhmon<|<mikhmon','mikhmon>|>aWNlbA==');
$data['session549'] = array ('1'=>'session549!','session549@|@','session549#|#','session549%','session549^','session549&Rp','session549*','session549(','session549)','session549=30','session549@!@disable','session549#!#');
$data['VICOTECH'] = array ('1'=>'VICOTECH!10.8.0.2','VICOTECH@|@admin','VICOTECH#|#mZOVaWJj','VICOTECH%FastNet','VICOTECH^hot.spot','VICOTECH&UGX','VICOTECH*','VICOTECH(','VICOTECH)','VICOTECH=30','VICOTECH@!@disable','VICOTECH#!#');
"""

# Write to temp file on host then copy into container
sftp = client.open_sftp()
with sftp.open('/tmp/config_fixed.php', 'w') as f:
    f.write(fixed)
sftp.close()

out, err = run("docker cp /tmp/config_fixed.php mikhmon-app:/var/www/html/config/config.php")
print("Copy result:", out, err)

# Verify
out, err = run("docker exec mikhmon-app cat /var/www/html/config/config.php")
print("\nFixed config:\n", out)

# Test URL
out, err = run('curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/index.php?admin&login&user=mikhmon&pass=1234&session=vicotech-fastnet"')
print("\nURL test:", out)

client.close()
print("Done.")

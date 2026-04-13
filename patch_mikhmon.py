import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

# Read current index.php
content = run('cat /root/mikhmon-v3/index.php')

# Check if already patched
if 'spotpay_token' in content:
    print("Already patched")
else:
    # Add SpotPay token bypass right after session_start()
    # When ?spotpay_token=TOKEN is in URL, auto-login and go to session
    bypass = """
// SpotPay auto-login bypass
if (isset($_GET['spotpay_token']) && isset($_GET['session'])) {
    $token_file = '/tmp/spotpay_token_' . $_GET['spotpay_token'];
    if (file_exists($token_file) && (time() - filemtime($token_file)) < 60) {
        $_SESSION['mikhmon'] = 'mikhmon';
        unlink($token_file); // one-time use
    }
}
// End SpotPay bypass
"""
    # Insert after session_start();
    patched = content.replace('session_start();\n', 'session_start();\n' + bypass, 1)
    
    # Write to temp file then copy
    sftp = client.open_sftp()
    with sftp.open('/tmp/index_patched.php', 'w') as f:
        f.write(patched)
    sftp.close()
    
    out = run('cp /tmp/index_patched.php /root/mikhmon-v3/index.php')
    print("Patched index.php:", out or "done")
    
    # Verify
    print("Verify:", run('grep -A3 "spotpay_token" /root/mikhmon-v3/index.php | head -5'))

client.close()

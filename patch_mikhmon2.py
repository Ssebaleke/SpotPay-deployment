import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

content = run('cat /root/mikhmon-v3/index.php')

if 'spotpay_token' in content:
    print("Already patched")
else:
    bypass = (
        "\n// SpotPay auto-login bypass\n"
        "if (isset($_GET['spotpay_token']) && isset($_GET['session'])) {\n"
        "    $token_file = '/tmp/spotpay_token_' . preg_replace('/[^a-zA-Z0-9]/', '', $_GET['spotpay_token']);\n"
        "    if (file_exists($token_file) && (time() - filemtime($token_file)) < 60) {\n"
        "        $_SESSION['mikhmon'] = 'mikhmon';\n"
        "        unlink($token_file);\n"
        "    }\n"
        "}\n"
        "// End SpotPay bypass\n"
    )

    # Try both CRLF and LF
    if 'session_start();\r\n' in content:
        patched = content.replace('session_start();\r\n', 'session_start();\r\n' + bypass, 1)
        print("Replaced CRLF version")
    else:
        patched = content.replace('session_start();\n', 'session_start();\n' + bypass, 1)
        print("Replaced LF version")

    sftp = client.open_sftp()
    with sftp.open('/tmp/index_patched.php', 'w') as f:
        f.write(patched)
    sftp.close()

    run('cp /tmp/index_patched.php /root/mikhmon-v3/index.php')
    
    # Verify
    result = run('grep -c "spotpay_token" /root/mikhmon-v3/index.php')
    print("spotpay_token occurrences:", result)
    print("First 40 lines:")
    print(run('head -40 /root/mikhmon-v3/index.php'))

client.close()

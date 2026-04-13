import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

content = run('cat /root/mikhmon-v3/index.php')

# Replace the old bypass with a fixed version using str_replace not preg_replace
old_bypass = (
    "// SpotPay auto-login bypass\n"
    "if (isset($_GET['spotpay_token']) && isset($_GET['session'])) {\n"
    "    $token_file = '/tmp/spotpay_token_' . preg_replace('/[^a-zA-Z0-9]/', '', $_GET['spotpay_token']);\n"
    "    if (file_exists($token_file) && (time() - filemtime($token_file)) < 60) {\n"
    "        $_SESSION['mikhmon'] = 'mikhmon';\n"
    "        unlink($token_file);\n"
    "    }\n"
    "}\n"
    "// End SpotPay bypass\n"
)

new_bypass = (
    "// SpotPay auto-login bypass\n"
    "if (isset($_GET['spotpay_token']) && isset($_GET['session'])) {\n"
    "    $raw = $_GET['spotpay_token'];\n"
    "    $safe = '';\n"
    "    for ($i = 0; $i < strlen($raw); $i++) {\n"
    "        $c = $raw[$i];\n"
    "        if (ctype_alnum($c)) $safe .= $c;\n"
    "    }\n"
    "    $token_file = '/tmp/spotpay_token_' . $safe;\n"
    "    if ($safe && file_exists($token_file) && (time() - filemtime($token_file)) < 60) {\n"
    "        $_SESSION['mikhmon'] = 'mikhmon';\n"
    "        unlink($token_file);\n"
    "    }\n"
    "}\n"
    "// End SpotPay bypass\n"
)

if old_bypass in content:
    patched = content.replace(old_bypass, new_bypass)
    sftp = client.open_sftp()
    with sftp.open('/tmp/index_fixed.php', 'w') as f:
        f.write(patched)
    sftp.close()
    run('cp /tmp/index_fixed.php /root/mikhmon-v3/index.php')
    print("Fixed bypass patch applied")
elif new_bypass in content:
    print("Already has fixed bypass")
else:
    print("Bypass not found — content snippet:")
    idx = content.find('spotpay_token')
    print(repr(content[max(0,idx-50):idx+200]))

client.close()

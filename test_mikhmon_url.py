import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('68.168.222.37', username='root', password='Vico@2026', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='ignore').strip()

# Read config inside container
print("=== config.php inside container ===")
print(run("docker exec mikhmon-app cat /var/www/html/config/config.php"))

# Test the bypass URL
print("\n=== Testing bypass URL ===")
print(run('curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/index.php?admin&login&user=mikhmon&pass=1234&session=vicotech-fastnet"'))

# Test without session
print("\n=== Testing login without session ===")
print(run('curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/index.php?admin&login&user=mikhmon&pass=1234"'))

client.close()

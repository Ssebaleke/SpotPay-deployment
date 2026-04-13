import requests, warnings
warnings.filterwarnings('ignore')

resp = requests.get('https://spotpay.it.com/locations/4/vpn-script.rsc', timeout=15)
lines = resp.text.split('\n')
for i, line in enumerate(lines, 1):
    print(f"{i:3}: ({len(line):3} chars) {line}")

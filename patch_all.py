import zipfile, os

src = 'media/portal_templates/hotspot.zip'
tmp = src + '.tmp'

new_login = open(r'C:\Users\Administrator\Desktop\SpotPay files\hotspot\login.html', encoding='utf-8').read()
new_portal = open(r'C:\Users\Administrator\Desktop\SpotPay files\hotspot\js\portal.js', encoding='utf-8').read()

with zipfile.ZipFile(src, 'r') as zin:
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.endswith('login.html'):
                zout.writestr(item, new_login.encode('utf-8'))
            elif item.filename.endswith('js/portal.js'):
                zout.writestr(item, new_portal.encode('utf-8'))
            else:
                zout.writestr(item, zin.read(item.filename))

os.replace(tmp, src)

with zipfile.ZipFile(src, 'r') as zf:
    login_ok = 'urlParams.get' in zf.read('hotspot/login.html').decode('utf-8', 'ignore')
    portal_ok = 'subscription_active' in zf.read('hotspot/js/portal.js').decode('utf-8', 'ignore')

with open('patch_result.txt', 'w') as f:
    f.write(f"login.html: {'OK' if login_ok else 'FAILED'}\nportal.js: {'OK' if portal_ok else 'FAILED'}")

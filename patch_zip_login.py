import zipfile, os

src = 'media/portal_templates/hotspot.zip'
tmp = src + '.tmp'

new_login = open(
    r'C:\Users\Administrator\Desktop\SpotPay files\hotspot\login.html',
    encoding='utf-8'
).read()

with zipfile.ZipFile(src, 'r') as zin:
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.endswith('login.html'):
                zout.writestr(item, new_login.encode('utf-8'))
            else:
                zout.writestr(item, zin.read(item.filename))

os.replace(tmp, src)

with zipfile.ZipFile(src, 'r') as zf:
    c = zf.read('hotspot/login.html').decode('utf-8', 'ignore')
    ok = 'urlParams.get' in c
    with open('patch_zip_login_result.txt', 'w') as f:
        f.write('OK - SMS fix confirmed in ZIP' if ok else 'FAILED')

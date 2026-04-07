import zipfile, os

src = 'media/portal_templates/hotspot.zip'
tmp = src + '.tmp'

new_portal_js = open('portal_api/static/portal_api/js/portal.js', encoding='utf-8').read()

with zipfile.ZipFile(src, 'r') as zin:
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.endswith('js/portal.js'):
                zout.writestr(item, new_portal_js.encode('utf-8'))
            else:
                zout.writestr(item, zin.read(item.filename))

os.replace(tmp, src)

# verify
with zipfile.ZipFile(src, 'r') as zf:
    c = zf.read('hotspot/js/portal.js').decode('utf-8', 'ignore')
    result = 'CHAP fix OK' if 'doLogin()' in c else 'FAILED - doLogin not found'

with open('patch_result.txt', 'w') as f:
    f.write(result)

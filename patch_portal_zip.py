"""
Run this on the server to patch the portal ZIP with auto-login support.
Usage: python patch_portal_zip.py
"""
import zipfile, os, glob

# Find the ZIP
media_dir = "/app/media/portal_templates"
zips = glob.glob(os.path.join(media_dir, "*.zip"))
if not zips:
    print("No ZIP found in", media_dir)
    exit(1)

src = zips[0]
tmp = src + ".tmp"
print("Patching:", src)

with zipfile.ZipFile(src, 'r') as zin:
    # Find login.html inside zip
    login_name = None
    for name in zin.namelist():
        if name.endswith('login.html') and 'MACOSX' not in name:
            login_name = name
            break

    if not login_name:
        print("login.html not found in ZIP")
        exit(1)

    print("Found:", login_name)
    content = zin.read(login_name).decode('utf-8', errors='ignore')

    if 'AUTO-LOGIN' in content:
        print("Already patched. Nothing to do.")
        exit(0)

    # Inject auto-login script before </body>
    auto_login = """
<!-- AUTO-LOGIN: if redirected back with ?username=CODE after payment -->
<script>
(function () {
    var params = new URLSearchParams(window.location.search);
    var username = params.get('username');
    var password = params.get('password');
    if (username) {
        var form = document.login;
        if (form) {
            form.username.value = username;
            form.password.value = password || username;
            form.submit();
        }
    }
})();
</script>
"""
    patched = content.replace('</body>', auto_login + '\n</body>')

    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == login_name:
                zout.writestr(item, patched.encode('utf-8'))
            else:
                zout.writestr(item, zin.read(item.filename))

os.replace(tmp, src)
print("Done. ZIP patched successfully.")

"""
CompanyAI — Tüm Platformlar İçin Toplu Build
Kullanım:
    python desktop/build_all.py                 # Sadece Windows (S1 + S2)
    python desktop/build_all.py --android       # Windows + Android APK
    python desktop/build_all.py --linux         # Windows + Linux
    python desktop/build_all.py --all           # Tüm platformlar
    python desktop/build_all.py --upload        # Build + sunuculara yükle

Çıktı Dosyaları (dist/):
    CompanyAI.exe       → Windows S1  (pywebview + PyInstaller)
    CompanyAI_S2.exe    → Windows S2  (pywebview + PyInstaller)
    CompanyAI-Linux     → Linux x86_64 (PyInstaller, sunucuda build)
    CompanyAI.apk       → Android APK (Capacitor + Gradle)
    CompanyAI.app.zip   → macOS       (Mac'te build_mac.sh ile)

Platform Gereksinimleri:
    Windows  → pywebview + pyinstaller (bu makine)
    Linux    → SSH ile sunucuda build (gir1.2-webkit2-4.0 gerekli)
    Android  → JDK + Android SDK + Capacitor
    macOS    → macOS makine + pywebview + pyinstaller
    iOS      → macOS + Xcode + Apple Developer Account
"""

import os
import sys
import re
import shutil
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_PY = os.path.join(ROOT, "desktop", "app.py")
SPEC = os.path.join(ROOT, "desktop", "companyai.spec")
DIST = os.path.join(ROOT, "dist")
DESKTOP_DIR = os.path.join(ROOT, "desktop")


def set_server_id(path: str, server_id: int):
    """app.py içindeki SERVER_ID sabitini değiştir"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(
        r"^(SERVER_ID\s*=\s*)\d+",
        rf"\g<1>{server_id}",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build_exe():
    """PyInstaller ile exe oluştur"""
    cmd = [sys.executable, "-m", "PyInstaller", SPEC, "--noconfirm", "--clean"]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return result.returncode == 0


# ═══════════════════════════════════════════════════
#  Windows Build
# ═══════════════════════════════════════════════════
def build_windows():
    """Windows .exe build (S1 + S2)"""
    print("\n" + "═" * 50)
    print("  🪟  Windows Build (S1 + S2)")
    print("═" * 50)

    if sys.platform != "win32":
        print("  ⚠️  Windows build sadece Windows'ta yapılabilir")
        return False

    os.makedirs(DIST, exist_ok=True)
    exe_path = os.path.join(DIST, "CompanyAI.exe")

    # S1
    print("  [S1] SERVER_ID=1...")
    set_server_id(APP_PY, 1)
    if not build_exe():
        print("  ❌ S1 build başarısız!")
        set_server_id(APP_PY, 1)
        return False
    s1_size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0
    print(f"  ✅ S1: dist/CompanyAI.exe ({s1_size:,} bytes)")

    # S2
    print("  [S2] SERVER_ID=2...")
    set_server_id(APP_PY, 2)
    if not build_exe():
        print("  ❌ S2 build başarısız!")
        set_server_id(APP_PY, 1)
        return False

    s2_exe = os.path.join(DIST, "CompanyAI_S2.exe")
    if os.path.exists(s2_exe):
        os.remove(s2_exe)
    shutil.move(exe_path, s2_exe)
    s2_size = os.path.getsize(s2_exe)
    print(f"  ✅ S2: dist/CompanyAI_S2.exe ({s2_size:,} bytes)")

    # S1 geri build
    set_server_id(APP_PY, 1)
    build_exe()
    return True


# ═══════════════════════════════════════════════════
#  Linux Build (SSH ile sunucuda)
# ═══════════════════════════════════════════════════
def build_linux(host="192.168.0.12", key="keys/companyai_key"):
    """Linux binary — SSH ile sunucuda PyInstaller build"""
    print("\n" + "═" * 50)
    print("  🐧  Linux Build (uzak sunucu)")
    print("═" * 50)

    key_path = os.path.join(ROOT, key)
    if not os.path.exists(key_path):
        print(f"  ❌ SSH key bulunamadı: {key}")
        return False

    def ssh(cmd):
        return subprocess.run(
            ["ssh", "-i", key_path, "-o", "StrictHostKeyChecking=no", f"root@{host}", cmd],
            capture_output=True, text=True, timeout=300
        )

    def scp_to(local, remote):
        return subprocess.run(
            ["scp", "-i", key_path, local, f"root@{host}:{remote}"],
            capture_output=True, text=True, timeout=60
        )

    print("  Bağımlılıklar kontrol ediliyor...")
    ssh("apt-get install -y -qq gir1.2-webkit2-4.0 python3-gi python3-venv 2>/dev/null")

    print("  Dosyalar yükleniyor...")
    ssh("mkdir -p /tmp/desktop_build")
    scp_to(APP_PY, "/tmp/desktop_build/app.py")

    print("  PyInstaller build ediliyor...")
    build_cmd = """cd /tmp/desktop_build && \
python3 -m venv venv --system-site-packages 2>/dev/null || true; \
source venv/bin/activate; \
pip install --quiet pywebview pyinstaller 2>/dev/null; \
cat > spec.spec << 'EOF'
import os
block_cipher = None
ROOT = os.path.abspath(SPECPATH)
a = Analysis([os.path.join(ROOT, 'app.py')], pathex=[ROOT], binaries=[], datas=[],
    hiddenimports=['webview','webview.platforms.gtk','gi','gi.repository.Gtk','gi.repository.WebKit2'],
    excludes=['tkinter','matplotlib','numpy','pandas','scipy'], cipher=block_cipher, noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [], name='CompanyAI',
    debug=False, strip=True, upx=True, console=False, icon=None)
EOF
pyinstaller spec.spec --noconfirm --clean 2>&1 | tail -3; \
ls -lh dist/CompanyAI 2>/dev/null && echo BUILD_OK || echo BUILD_FAIL"""

    result = ssh(build_cmd)
    if "BUILD_OK" not in result.stdout:
        print(f"  ❌ Linux build başarısız")
        return False

    # Downloads'a kopyala
    ssh("cp /tmp/desktop_build/dist/CompanyAI /var/www/html/downloads/CompanyAI-Linux; chmod 644 /var/www/html/downloads/CompanyAI-Linux")

    # Lokale de indir
    linux_bin = os.path.join(DIST, "CompanyAI-Linux")
    subprocess.run(
        ["scp", "-i", key_path, f"root@{host}:/tmp/desktop_build/dist/CompanyAI", linux_bin],
        capture_output=True, text=True, timeout=60
    )

    if os.path.exists(linux_bin):
        size_mb = os.path.getsize(linux_bin) / (1024 * 1024)
        print(f"  ✅ dist/CompanyAI-Linux ({size_mb:.1f} MB)")
        return True
    return False


# ═══════════════════════════════════════════════════
#  Android APK Build
# ═══════════════════════════════════════════════════
def build_android():
    """Android APK — Capacitor + Gradle"""
    print("\n" + "═" * 50)
    print("  🤖  Android APK Build")
    print("═" * 50)

    frontend_dir = os.path.join(ROOT, "frontend")
    android_dir = os.path.join(frontend_dir, "android")

    if not os.path.exists(android_dir):
        print("  ❌ frontend/android dizini yok — 'npx cap add android' çalıştırın")
        return False

    # Android SDK
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not android_home:
        for candidate in [
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk"),
            os.path.expanduser("~/Android/Sdk"),
        ]:
            if os.path.exists(candidate):
                android_home = candidate
                break
    if not android_home or not os.path.exists(android_home):
        print("  ❌ Android SDK bulunamadı")
        return False

    os.environ["ANDROID_HOME"] = android_home
    os.environ["ANDROID_SDK_ROOT"] = android_home
    print(f"  SDK: {android_home}")

    # Java
    java_home = os.environ.get("JAVA_HOME", "")
    if not java_home or not os.path.exists(java_home):
        java_dir = r"C:\Program Files\Java"
        if os.path.exists(java_dir):
            jdks = sorted(os.listdir(java_dir), reverse=True)
            if jdks:
                java_home = os.path.join(java_dir, jdks[0])
                os.environ["JAVA_HOME"] = java_home

    # Capacitor sync
    print("  Capacitor sync...")
    subprocess.run(["npx", "cap", "sync", "android"], cwd=frontend_dir,
                    capture_output=True, text=True, shell=True)

    # Gradle build
    print("  Gradle assembleRelease...")
    gradlew = os.path.join(android_dir, "gradlew.bat" if sys.platform == "win32" else "gradlew")
    result = subprocess.run([gradlew, "assembleRelease"], cwd=android_dir,
                            capture_output=True, text=True, shell=(sys.platform == "win32"))
    if result.returncode != 0:
        print(f"  ❌ Gradle build başarısız")
        return False

    # APK sign
    unsigned = os.path.join(android_dir, "app", "build", "outputs", "apk", "release", "app-release-unsigned.apk")
    if not os.path.exists(unsigned):
        print("  ❌ APK bulunamadı")
        return False

    keystore = os.path.join(DESKTOP_DIR, "companyai-release.keystore")
    signed = os.path.join(DIST, "CompanyAI.apk")
    aligned = os.path.join(DIST, "CompanyAI-aligned.apk")

    for f in [signed, aligned]:
        if os.path.exists(f):
            os.remove(f)

    if os.path.exists(keystore):
        bt_dir = os.path.join(android_home, "build-tools")
        bt_versions = sorted(os.listdir(bt_dir), reverse=True) if os.path.exists(bt_dir) else []
        if bt_versions:
            bt = os.path.join(bt_dir, bt_versions[0])
            zipalign = os.path.join(bt, "zipalign.exe" if sys.platform == "win32" else "zipalign")
            apksigner = os.path.join(bt, "apksigner.bat" if sys.platform == "win32" else "apksigner")

            subprocess.run([zipalign, "-p", "4", unsigned, aligned], check=True, capture_output=True)
            subprocess.run([
                apksigner, "sign",
                "--ks", keystore, "--ks-key-alias", "companyai",
                "--ks-pass", "pass:companyai123", "--key-pass", "pass:companyai123",
                "--out", signed, aligned
            ], check=True, capture_output=True, shell=(sys.platform == "win32"))
            if os.path.exists(aligned):
                os.remove(aligned)
    else:
        shutil.copy2(unsigned, signed)

    if os.path.exists(signed):
        size_mb = os.path.getsize(signed) / (1024 * 1024)
        print(f"  ✅ dist/CompanyAI.apk ({size_mb:.1f} MB)")
        return True
    return False


# ═══════════════════════════════════════════════════
#  Sunuculara Yükle
# ═══════════════════════════════════════════════════
def upload_to_servers():
    """Tüm dosyaları S1 + S2'ye yükle"""
    print("\n" + "═" * 50)
    print("  📤  Sunuculara Yükleniyor")
    print("═" * 50)

    key_path = os.path.join(ROOT, "keys", "companyai_key")

    files_s1 = {
        "CompanyAI.exe": "CompanyAI.exe",
        "CompanyAI-Linux": "CompanyAI-Linux",
        "CompanyAI.apk": "CompanyAI.apk",
        "CompanyAI.app.zip": "CompanyAI.app.zip",
    }
    files_s2 = {
        "CompanyAI_S2.exe": "CompanyAI.exe",
        "CompanyAI-Linux": "CompanyAI-Linux",
        "CompanyAI.apk": "CompanyAI.apk",
        "CompanyAI.app.zip": "CompanyAI.app.zip",
    }

    # S1
    print("\n  [S1] 192.168.0.12")
    subprocess.run(["ssh", "-i", key_path, "root@192.168.0.12", "mkdir -p /var/www/html/downloads"],
                    capture_output=True, timeout=15)
    for local_name, remote_name in files_s1.items():
        local_path = os.path.join(DIST, local_name)
        if os.path.exists(local_path):
            r = subprocess.run(["scp", "-i", key_path, local_path,
                                f"root@192.168.0.12:/var/www/html/downloads/{remote_name}"],
                               capture_output=True, text=True, timeout=120)
            status = "✅" if r.returncode == 0 else "❌"
            print(f"    {status} {remote_name}")
        else:
            print(f"    ⏭️  {local_name} yok")
    subprocess.run(["ssh", "-i", key_path, "root@192.168.0.12",
                    "chmod 644 /var/www/html/downloads/*; systemctl reload nginx"],
                   capture_output=True, timeout=15)

    # S2 (paramiko)
    print("\n  [S2] 88.246.13.23")
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect("88.246.13.23", port=2013, username="root", password="Kc435102mn", timeout=15)
        ssh.exec_command("mkdir -p /var/www/html/downloads")
        sftp = ssh.open_sftp()
        for local_name, remote_name in files_s2.items():
            local_path = os.path.join(DIST, local_name)
            if os.path.exists(local_path):
                try:
                    sftp.put(local_path, f"/var/www/html/downloads/{remote_name}")
                    sftp.chmod(f"/var/www/html/downloads/{remote_name}", 0o644)
                    print(f"    ✅ {remote_name}")
                except Exception as e:
                    print(f"    ❌ {remote_name}: {e}")
            else:
                print(f"    ⏭️  {local_name} yok")
        sftp.close()
        ssh.exec_command("systemctl reload nginx")
        ssh.close()
    except Exception as e:
        print(f"    ❌ S2 bağlantı hatası: {e}")


# ═══════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════
def main():
    args = sys.argv[1:]
    do_all = "--all" in args
    do_linux = "--linux" in args or do_all
    do_android = "--android" in args or do_all
    do_upload = "--upload" in args

    os.makedirs(DIST, exist_ok=True)

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║  CompanyAI — Multi-Platform Build             ║")
    print("╚══════════════════════════════════════════════╝")

    results = {}

    # Windows
    if sys.platform == "win32":
        results["Windows"] = build_windows()

    # Linux
    if do_linux:
        results["Linux"] = build_linux()

    # Android
    if do_android:
        results["Android"] = build_android()

    # macOS/iOS bilgilendirme
    if do_all and sys.platform != "darwin":
        print("\n" + "═" * 50)
        print("  🍎  macOS / iOS — Mac gerekli")
        print("═" * 50)
        print("    macOS:  ./desktop/build_mac.sh")
        print("    iOS:    cd frontend && npx cap build ios")
        print("    (Build sonrası dist/ klasörüne kopyalayın)")

    # Upload
    if do_upload:
        upload_to_servers()

    # Özet
    print("\n" + "═" * 50)
    print("  📊 Build Özeti")
    print("═" * 50)
    for platform, success in results.items():
        print(f"    {'✅' if success else '❌'} {platform}")
    print()
    if os.path.exists(DIST):
        print("  📁 dist/ içeriği:")
        for f in sorted(os.listdir(DIST)):
            fp = os.path.join(DIST, f)
            if os.path.isfile(fp):
                size_mb = os.path.getsize(fp) / (1024 * 1024)
                print(f"    {f:30s} {size_mb:6.1f} MB")
    print()


if __name__ == "__main__":
    main()

"""Deploy script — CompanyAi → 192.168.0.12"""

import paramiko
import os
import sys
import time
import subprocess
import glob
from pathlib import Path
from scp import SCPClient

HOST = "192.168.0.12"
USER = "root"
PASSWORD = "435102"
KEY_PATH = Path("keys/companyai_key")
PUB_KEY_PATH = Path("keys/companyai_key.pub")
REMOTE_DIR = "/opt/companyai"

# ── Dosya listesi ────────────────────────────────────────────────
BACKEND_FILES = [
    "app/__init__.py",
    "app/config.py",
    "app/main.py",
    "app/api/__init__.py",
    "app/api/routes/__init__.py",
    "app/api/routes/admin.py",
    "app/api/routes/ask.py",
    "app/api/routes/auth.py",
    "app/api/routes/documents.py",
    "app/api/routes/memory.py",
    "app/api/routes/multimodal.py",
    "app/auth/__init__.py",
    "app/auth/jwt_handler.py",
    "app/auth/rbac.py",
    "app/core/__init__.py",
    "app/core/audit.py",
    "app/core/constants.py",
    "app/core/engine.py",
    "app/core/document_analyzer.py",
    "app/core/export_service.py",
    "app/api/routes/analyze.py",
    "app/api/routes/export.py",
    "app/db/__init__.py",
    "app/db/database.py",
    "app/db/models.py",
    "app/llm/__init__.py",
    "app/llm/client.py",
    "app/llm/local_llm.py",
    "app/llm/prompts.py",
    "app/llm/web_search.py",
    "app/llm/chat_examples.py",
    "app/llm/chat_patterns.json",
    "app/memory/__init__.py",
    "app/memory/vector_memory.py",
    "app/memory/persistent_memory.py",
    "app/rag/__init__.py",
    "app/rag/vector_store.py",
    "app/router/__init__.py",
    "app/router/router.py",
    "app/voice/__init__.py",
    "app/voice/field_assistant.py",
    "app/dashboard/__init__.py",
    "requirements.txt",
    "pyproject.toml",
]

ROOT_DOCS = [
    "reference.md",
    "NOTES.md",
    "README.md",
]

DATA_FILES = [
    "data/turkish_chat_dataset.json",
]


def create_ssh_client(use_key=True):
    """SSH bağlantısı oluştur."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if use_key and KEY_PATH.exists():
        try:
            pkey = paramiko.Ed25519Key.from_private_key_file(str(KEY_PATH))
            client.connect(HOST, username=USER, pkey=pkey, timeout=15)
            print(f"  ✅ SSH key ile bağlanıldı ({KEY_PATH})")
            return client
        except Exception as e:
            print(f"  ⚠️ Key ile bağlantı başarısız ({e}), şifre deneniyor...")

    client.connect(HOST, username=USER, password=PASSWORD, timeout=15)
    print("  ✅ Şifre ile bağlanıldı")
    return client


def run_cmd(ssh, cmd, check=True):
    """Uzak komut çalıştır ve çıktıyı döndür."""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if check and exit_code != 0:
        print(f"  ⚠️ Komut hata verdi (exit {exit_code}): {cmd}")
        if err:
            print(f"     STDERR: {err[:300]}")
    return out, err, exit_code


def install_ssh_key(ssh):
    """Public key'i sunucuya yükle."""
    pub_key = PUB_KEY_PATH.read_text().strip()
    print("\n📌 SSH public key sunucuya yükleniyor...")
    run_cmd(ssh, "mkdir -p ~/.ssh && chmod 700 ~/.ssh")
    # Aynı key zaten ekliyse tekrar ekleme
    out, _, _ = run_cmd(ssh, f'grep -c "companyai-deploy" ~/.ssh/authorized_keys 2>/dev/null || echo 0', check=False)
    if out.strip() == "0":
        run_cmd(ssh, f'echo "{pub_key}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys')
        print("  ✅ Public key authorized_keys'e eklendi")
    else:
        print("  ℹ️ Key zaten yüklü")


def upload_files(ssh):
    """Backend dosyalarını sunucuya yükle."""
    print("\n📦 Backend dosyaları yükleniyor...")

    # Uzak klasör yapısını oluştur
    remote_dirs = set()
    for f in BACKEND_FILES:
        d = os.path.dirname(f)
        if d:
            remote_dirs.add(f"{REMOTE_DIR}/{d}")
    for d in sorted(remote_dirs):
        run_cmd(ssh, f"mkdir -p {d}")

    with SCPClient(ssh.get_transport()) as scp:
        for local_rel in BACKEND_FILES:
            local_path = Path(local_rel)
            if not local_path.exists():
                print(f"  ⚠️ Yerel dosya bulunamadı: {local_rel}")
                continue
            remote_path = f"{REMOTE_DIR}/{local_rel}"
            scp.put(str(local_path), remote_path)
            print(f"  📄 {local_rel}")

        # Dokümanlar
        for doc in ROOT_DOCS:
            if Path(doc).exists():
                scp.put(doc, f"{REMOTE_DIR}/{doc}")
                print(f"  📄 {doc}")

        # Data dosyaları
        for data_file in DATA_FILES:
            local_path = Path(data_file)
            if local_path.exists():
                remote_path = f"{REMOTE_DIR}/{data_file}"
                # data/ klasörünü oluştur
                remote_dir = str(Path(remote_path).parent).replace("\\", "/")
                run_cmd(ssh, f"mkdir -p {remote_dir}", check=False)
                scp.put(str(local_path), remote_path)
                print(f"  📄 {data_file}")

    print("  ✅ Dosya yükleme tamamlandı")


def build_and_deploy_frontend(ssh):
    """Frontend'i lokal olarak build edip sunucuya yükle."""
    frontend_dir = Path("frontend")
    dist_dir = frontend_dir / "dist"
    
    if not (frontend_dir / "package.json").exists():
        print("\n⚠️ Frontend klasörü bulunamadı, atlanıyor...")
        return
    
    print("\n🏗️  Frontend build ediliyor...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(frontend_dir),
        capture_output=True, text=True, shell=True,
    )
    if result.returncode != 0:
        print(f"  ⚠️ Frontend build hatası: {result.stderr[:300]}")
        return
    print("  ✅ Frontend build başarılı")
    
    # Sunucudaki eski dosyaları temizle
    print("  📤 Frontend dosyaları sunucuya yükleniyor...")
    run_cmd(ssh, "rm -rf /var/www/html/assets/* && rm -f /var/www/html/index.html", check=False)
    
    # Yeni dosyaları yükle
    with SCPClient(ssh.get_transport()) as scp:
        # index.html
        index_file = dist_dir / "index.html"
        if index_file.exists():
            scp.put(str(index_file), "/var/www/html/index.html")
            print("  📄 index.html")
        
        # assets/
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            run_cmd(ssh, "mkdir -p /var/www/html/assets", check=False)
            for f in assets_dir.iterdir():
                if f.is_file():
                    scp.put(str(f), f"/var/www/html/assets/{f.name}")
                    print(f"  📄 assets/{f.name}")
    
    # İzinleri düzelt
    run_cmd(ssh, "chmod 644 /var/www/html/assets/* && chmod 755 /var/www/html/assets", check=False)
    print("  ✅ Frontend deploy tamamlandı")


def install_dependencies(ssh):
    """Sunucuda pip bağımlılıklarını güncelle."""
    print("\n📥 Bağımlılıklar yükleniyor (requirements.txt)...")
    out, err, code = run_cmd(ssh,
        f"cd {REMOTE_DIR} && pip install -r requirements.txt --quiet 2>&1 | tail -5",
        check=False
    )
    if out:
        print(f"  {out}")
    if code == 0:
        print("  ✅ Bağımlılıklar güncellendi")
    else:
        # pip3 dene
        out2, _, code2 = run_cmd(ssh,
            f"cd {REMOTE_DIR} && pip3 install -r requirements.txt --quiet 2>&1 | tail -5",
            check=False
        )
        if out2:
            print(f"  {out2}")
        print(f"  {'✅' if code2 == 0 else '⚠️'} pip3 ile denendi (exit {code2})")


def restart_services(ssh):
    """Backend servisini yeniden başlat."""
    print("\n🔄 Servisler yeniden başlatılıyor...")

    run_cmd(ssh, "systemctl daemon-reload")
    out, err, code = run_cmd(ssh, "systemctl restart companyai-backend", check=False)
    if code != 0:
        print(f"  ⚠️ Backend restart hatası: {err[:200]}")
    else:
        print("  ✅ companyai-backend yeniden başlatıldı")

    time.sleep(3)
    out, _, _ = run_cmd(ssh, "systemctl is-active companyai-backend", check=False)
    print(f"  Backend durumu: {out}")

    # Nginx reload
    run_cmd(ssh, "systemctl reload nginx 2>/dev/null || systemctl restart nginx 2>/dev/null", check=False)
    print("  ✅ Nginx reload edildi")


def verify_deployment(ssh):
    """Deploy'u doğrula."""
    print("\n🔍 Deployment doğrulanıyor...")

    # Servis durumu
    out, _, _ = run_cmd(ssh, "systemctl is-active companyai-backend", check=False)
    backend_ok = out.strip() == "active"
    print(f"  Backend: {'✅ active' if backend_ok else '❌ ' + out}")

    # API health check
    out, _, code = run_cmd(ssh, "curl -sk https://127.0.0.1/api/health 2>/dev/null || curl -s http://127.0.0.1:8000/api/health 2>/dev/null", check=False)
    print(f"  Health: {out[:200] if out else '❌ yanıt yok'}")

    # Son loglar
    out, _, _ = run_cmd(ssh, "journalctl -u companyai-backend --no-pager -n 5 2>/dev/null", check=False)
    if out:
        print(f"  Son loglar:\n    {out.replace(chr(10), chr(10) + '    ')}")

    return backend_ok


def main():
    print("=" * 60)
    print("  🚀 CompanyAi Deploy — 192.168.0.12")
    print("=" * 60)

    # 1. SSH bağlantısı (önce şifre ile, key'i yüklemek için)
    print("\n🔑 SSH bağlantısı kuruluyor...")
    ssh = create_ssh_client(use_key=False)

    # 2. SSH key yükle
    install_ssh_key(ssh)
    ssh.close()

    # 3. Artık key ile bağlan
    print("\n🔑 SSH key ile yeniden bağlanılıyor...")
    ssh = create_ssh_client(use_key=True)

    # 4. Dosyaları yükle
    upload_files(ssh)

    # 4.5. Frontend build & deploy
    build_and_deploy_frontend(ssh)

    # 5. Bağımlılıkları yükle
    install_dependencies(ssh)

    # 6. Servisleri yeniden başlat
    restart_services(ssh)

    # 7. Doğrula
    ok = verify_deployment(ssh)

    ssh.close()

    print("\n" + "=" * 60)
    if ok:
        print("  ✅ DEPLOYMENT BAŞARILI")
    else:
        print("  ⚠️ DEPLOYMENT TAMAMLANDI — servis durumunu kontrol edin")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

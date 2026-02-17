"""Deploy script — CompanyAi → Çoklu Sunucu
Versiyon: app/config.py + frontend/src/constants.ts eşleşmeli.
Kullanım:
  python deploy_now.py          → Sunucu 1 (192.168.0.12)
  python deploy_now.py --server2  → Sunucu 2 (88.246.13.23:2013)
  python deploy_now.py --all      → Her iki sunucuya deploy
"""

import paramiko
import os
import sys
import time
import subprocess
import glob
from pathlib import Path
from scp import SCPClient

# ── Sunucu yapılandırmaları ──────────────────────────────────────
# GÜVENLİK: Credentials .env dosyasından veya environment variable'lardan okunur.
# Dosya: .env.deploy (gitignore'da olmalı)
_ENV_FILE = Path(".env.deploy")

def _load_deploy_env() -> dict:
    """Deploy credentials'ı .env.deploy dosyasından veya env vars'dan yükle."""
    env = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    # Environment variables override file
    for key in ["S1_HOST", "S1_PORT", "S1_USER", "S1_PASS",
                "S2_HOST", "S2_PORT", "S2_USER", "S2_PASS"]:
        val = os.environ.get(key)
        if val:
            env[key] = val
    return env

_deploy_env = _load_deploy_env()

SERVERS = {
    "server1": {
        "host": _deploy_env.get("S1_HOST", "192.168.0.12"),
        "port": int(_deploy_env.get("S1_PORT", "22")),
        "user": _deploy_env.get("S1_USER", "root"),
        "password": _deploy_env.get("S1_PASS", ""),
        "key_path": Path("keys/companyai_key"),
        "pub_key_path": Path("keys/companyai_key.pub"),
        "key_comment": "companyai-deploy",
        "pip_cmd": "pip",           # Server 1 — sistem Python
        "uvicorn_path": "/usr/local/bin/uvicorn",
    },
    "server2": {
        "host": _deploy_env.get("S2_HOST", "88.246.13.23"),
        "port": int(_deploy_env.get("S2_PORT", "2013")),
        "user": _deploy_env.get("S2_USER", "root"),
        "password": _deploy_env.get("S2_PASS", ""),
        "key_path": Path("keys/server2_key"),
        "pub_key_path": Path("keys/server2_key.pub"),
        "key_comment": "companyai-server2",
        "pip_cmd": "/opt/companyai/venv/bin/pip",   # Server 2 — venv
        "uvicorn_path": "/opt/companyai/venv/bin/uvicorn",
    },
}

# Aktif sunucu (argümanla değişir)
HOST = SERVERS["server1"]["host"]
USER = SERVERS["server1"]["user"]
PASSWORD = SERVERS["server1"]["password"]
SSH_PORT = SERVERS["server1"]["port"]
KEY_PATH = Path("keys/companyai_key")
PUB_KEY_PATH = Path("keys/companyai_key.pub")
KEY_COMMENT = "companyai-deploy"
PIP_CMD = "pip"
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
    "app/core/knowledge_extractor.py",
    "app/core/document_analyzer.py",
    "app/core/export_service.py",
    "app/core/tool_registry.py",
    "app/core/reasoning.py",
    "app/core/forecasting.py",
    "app/core/kpi_engine.py",
    "app/core/textile_knowledge.py",
    "app/core/risk_analyzer.py",
    "app/core/reflection.py",
    "app/core/agent_pipeline.py",
    "app/core/scenario_engine.py",
    "app/core/monte_carlo.py",
    "app/core/decision_ranking.py",
    "app/core/governance.py",
    "app/core/experiment_layer.py",
    "app/core/graph_impact.py",
    "app/core/numerical_validation.py",
    "app/core/sql_generator.py",
    "app/core/model_registry.py",
    "app/core/data_versioning.py",
    "app/core/hitl.py",
    "app/core/monitoring.py",
    "app/core/bottleneck_engine.py",
    "app/core/executive_health.py",
    "app/core/insight_engine.py",
    "app/core/textile_vision.py",
    "app/core/explainability.py",
    "app/core/token_budget.py",
    "app/core/ocr_engine.py",
    "app/core/chart_engine.py",
    "app/core/report_templates.py",
    "app/core/whisper_stt.py",
    "app/core/meta_learning.py",
    "app/core/self_improvement.py",
    "app/core/multi_agent_debate.py",
    "app/core/causal_inference.py",
    "app/core/strategic_planner.py",
    "app/core/executive_intelligence.py",
    "app/core/knowledge_graph.py",
    "app/core/decision_gatekeeper.py",
    "app/core/uncertainty_quantification.py",
    "app/core/decision_quality.py",
    "app/core/kpi_impact.py",
    "app/core/decision_memory.py",
    "app/core/executive_digest.py",
    "app/core/ood_detector.py",
    "app/core/module_synapse.py",
    # v5.5.0 Enterprise Platform
    "app/core/event_bus.py",
    "app/core/orchestrator.py",
    "app/core/policy_engine.py",
    "app/core/observability.py",
    "app/core/security.py",
    "app/api/routes/analyze.py",
    "app/api/routes/export.py",
    "app/api/routes/backup.py",
    "app/api/routes/metrics.py",
    "app/db/__init__.py",
    "app/db/database.py",
    "app/db/models.py",
    "app/llm/__init__.py",
    "app/llm/client.py",
    "app/llm/gpu_config.py",
    "app/llm/local_llm.py",
    "app/llm/prompts.py",
    "app/llm/web_search.py",
    "app/llm/chat_examples.py",
    "app/llm/chat_patterns.json",
    "app/llm/structured_output.py",
    "app/memory/__init__.py",
    "app/memory/vector_memory.py",
    "app/memory/persistent_memory.py",
    "app/rag/__init__.py",
    "app/rag/vector_store.py",
    "app/rag/pdf_images.py",
    "app/cache/__init__.py",
    "app/cache/redis_cache.py",
    "app/router/__init__.py",
    "app/router/router.py",
    "app/voice/__init__.py",
    "app/voice/field_assistant.py",
    "app/dashboard/__init__.py",
    "requirements.txt",
    "pyproject.toml",
    "gunicorn.conf.py",
]

ROOT_DOCS = [
    "reference.md",
    "NOTES.md",
    "README.md",
    "extract_existing_pdf_images.py",
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
            client.connect(HOST, port=SSH_PORT, username=USER, pkey=pkey, timeout=15,
                           allow_agent=False, look_for_keys=False)
            print(f"  ✅ SSH key ile bağlanıldı ({KEY_PATH})")
            return client
        except Exception as e:
            print(f"  ⚠️ Key ile bağlantı başarısız ({e}), şifre deneniyor...")

    client.connect(HOST, port=SSH_PORT, username=USER, password=PASSWORD, timeout=15,
                   allow_agent=False, look_for_keys=False)
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
    out, _, _ = run_cmd(ssh, f'grep -c "{KEY_COMMENT}" ~/.ssh/authorized_keys 2>/dev/null || echo 0', check=False)
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
        f"cd {REMOTE_DIR} && {PIP_CMD} install -r requirements.txt --quiet 2>&1 | tail -5",
        check=False
    )
    if out:
        print(f"  {out}")
    if code == 0:
        print("  ✅ Bağımlılıklar güncellendi")
    else:
        # Alternatif pip dene
        alt_pip = "pip3" if PIP_CMD == "pip" else "pip"
        out2, _, code2 = run_cmd(ssh,
            f"cd {REMOTE_DIR} && {alt_pip} install -r requirements.txt --quiet 2>&1 | tail -5",
            check=False
        )
        if out2:
            print(f"  {out2}")
        print(f"  {'✅' if code2 == 0 else '⚠️'} alternatif pip ile denendi (exit {code2})")


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
    """Deploy'u doğrula — retry ile health check."""
    print("\n🔍 Deployment doğrulanıyor...")

    # Servis durumu
    out, _, _ = run_cmd(ssh, "systemctl is-active companyai-backend", check=False)
    backend_ok = out.strip() == "active"
    print(f"  Backend: {'✅ active' if backend_ok else '❌ ' + out}")

    # API health check — retry (uvicorn başlaması ~8sn sürebilir)
    import time as _t
    health_ok = False
    for attempt in range(4):
        if attempt > 0:
            _t.sleep(4)
        out, _, code = run_cmd(ssh, "curl -sk https://127.0.0.1/api/health 2>/dev/null || curl -s http://127.0.0.1:8000/api/health 2>/dev/null", check=False)
        if out and "502" not in out and "error" not in out.lower():
            health_ok = True
            print(f"  Health: ✅ {out[:200]}")
            break
        elif attempt < 3:
            print(f"  Health: ⏳ Bekleniyor... (deneme {attempt+1}/4)")
    if not health_ok:
        print(f"  Health: {out[:200] if out else '❌ yanıt yok'}")

    # Son loglar
    out, _, _ = run_cmd(ssh, "journalctl -u companyai-backend --no-pager -n 5 2>/dev/null", check=False)
    if out:
        print(f"  Son loglar:\n    {out.replace(chr(10), chr(10) + '    ')}")

    return backend_ok


def set_active_server(name):
    """Global değişkenleri seçilen sunucuya ayarla."""
    global HOST, USER, PASSWORD, SSH_PORT, KEY_PATH, PUB_KEY_PATH, KEY_COMMENT, PIP_CMD
    cfg = SERVERS[name]
    HOST = cfg["host"]
    SSH_PORT = cfg["port"]
    USER = cfg["user"]
    PASSWORD = cfg["password"]
    KEY_PATH = cfg["key_path"]
    PUB_KEY_PATH = cfg["pub_key_path"]
    KEY_COMMENT = cfg["key_comment"]
    PIP_CMD = cfg["pip_cmd"]


def deploy_to_server(server_name):
    """Tek bir sunucuya deploy yap."""
    set_active_server(server_name)
    cfg = SERVERS[server_name]

    print("\n" + "=" * 60)
    print(f"  🚀 CompanyAi Deploy — {cfg['host']}:{cfg['port']} ({server_name})")
    print("=" * 60)

    # 1. SSH bağlantısı (key varsa önce key dene, yoksa şifre)
    print("\n🔑 SSH bağlantısı kuruluyor...")
    ssh = create_ssh_client(use_key=True)

    # 2. SSH key yükle (idempotent — zaten varsa atlar)
    install_ssh_key(ssh)

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
        print(f"  ✅ DEPLOYMENT BAŞARILI — {cfg['host']}")
    else:
        print(f"  ⚠️ DEPLOYMENT TAMAMLANDI — {cfg['host']} — servis durumunu kontrol edin")
    print("=" * 60)
    return ok


def main():
    # ── VERSİYON KONTROLÜ ──────────────────────────────────────
    try:
        import re
        config_path = Path("app/config.py")
        const_path = Path("frontend/src/constants.ts")
        be_ver = re.search(r'APP_VERSION\s*=\s*["\'](.+?)["\']', config_path.read_text()).group(1)
        fe_ver = re.search(r'APP_VERSION\s*=\s*["\'](.+?)["\']', const_path.read_text()).group(1)
        print(f"\n📋 Versiyon Kontrolü:")
        print(f"   Backend  (config.py):    v{be_ver}")
        print(f"   Frontend (constants.ts): v{fe_ver}")
        if be_ver != fe_ver:
            print(f"   ⚠️  UYARI: Backend ve Frontend versiyonları FARKLI!")
            ans = input("   Devam etmek istiyor musunuz? (e/h): ").strip().lower()
            if ans != 'e':
                print("   ❌ Deploy iptal edildi. Versiyonları eşitleyin.")
                return 1
        else:
            print(f"   ✅ Versiyonlar eşleşiyor: v{be_ver}")
    except Exception as e:
        print(f"   ⚠️  Versiyon okunamadı: {e}")

    # ── Hedef sunucu seçimi ──────────────────────────────────
    targets = []
    if "--server2" in sys.argv:
        targets = ["server2"]
    elif "--all" in sys.argv:
        targets = ["server1", "server2"]
    else:
        targets = ["server1"]

    print(f"\n🎯 Hedef: {', '.join(t + ' (' + SERVERS[t]['host'] + ')' for t in targets)}")

    results = {}
    for t in targets:
        results[t] = deploy_to_server(t)

    # Özet
    if len(targets) > 1:
        print("\n" + "=" * 60)
        print("  📊 DEPLOY ÖZET:")
        for t, ok in results.items():
            s = "✅ BAŞARILI" if ok else "⚠️ KONTROL ET"
            print(f"     {SERVERS[t]['host']}: {s}")
        print("=" * 60)

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

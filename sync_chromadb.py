"""CompanyAI Senkronizasyon Script'i — Server 2 → Server 1

Saatlik olarak çalışır:
1. ChromaDB verilerini (dokümanlar + hafıza) Server 2 → Server 1 senkronize eder
2. Kullanıcı hesaplarını Server 2 → Server 1 senkronize eder

Mevcut veriler korunur, sadece yeni kayıtlar eklenir.

Kullanım:
  python sync_chromadb.py                → Tam senkronizasyon (chromadb + kullanıcı)
  python sync_chromadb.py --dry-run      → Sadece kontrol, değişiklik yapmaz
  python sync_chromadb.py --users-only   → Sadece kullanıcı sync
  python sync_chromadb.py --chromadb-only → Sadece ChromaDB sync

Cron (her saat):
  0 * * * * /opt/companyai/venv/bin/python /opt/companyai/sync_chromadb.py >> /var/log/companyai_sync.log 2>&1
"""

import paramiko
import json
import os
import sys
import time
import tempfile
from pathlib import Path
from datetime import datetime
from scp import SCPClient

# ── Sunucu Yapılandırması ────────────────────────────────────────
SOURCE_SERVER = {
    "name": "server2",
    "host": "88.246.13.23",
    "port": 2013,
    "user": "root",
    "password": "Kc435102mn",
    "key_path": Path("keys/server2_key"),
}

TARGET_SERVER = {
    "name": "server1",
    "host": "192.168.0.12",
    "port": 22,
    "user": "root",
    "password": "435102",
    "key_path": Path("keys/companyai_key"),
}

CHROMA_DATA_DIR = "/opt/companyai/data/chromadb"
REMOTE_SYNC_DIR = "/tmp/companyai_sync"

# Bu script sunucuya yüklenip chromadb export/import yapmak için çalıştırılacak
REMOTE_EXPORT_SCRIPT = r'''
#!/usr/bin/env python3
"""ChromaDB Export Helper — Server 2'den veri dışa aktar"""
import json
import sys
import os

# ChromaDB path
CHROMA_DIR = "/opt/companyai/data/chromadb"
OUTPUT_DIR = "/tmp/companyai_sync"

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            import numpy as np
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return super().default(obj)

def export_all():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DIR)
    except Exception as e:
        print(f"HATA: ChromaDB baglanti hatasi: {e}", file=sys.stderr)
        sys.exit(1)
    
    collections = client.list_collections()
    print(f"Toplam {len(collections)} koleksiyon bulundu")
    
    all_data = {}
    for col in collections:
        col_name = col.name
        print(f"  Export: {col_name}")
        
        # Tum verileri al (embeddings dahil)
        data = col.get(include=["documents", "metadatas", "embeddings"])
        
        if not data or not data.get("ids"):
            print(f"    -> Bos koleksiyon, atlaniyor")
            continue
        
        count = len(data["ids"])
        print(f"    -> {count} kayit")
        
        # Embeddings'i list'e cevir (numpy array olabilir)
        embeddings = data.get("embeddings", [])
        if embeddings is not None and len(embeddings) > 0:
            clean_embeds = []
            for emb in embeddings:
                if hasattr(emb, 'tolist'):
                    clean_embeds.append(emb.tolist())
                elif isinstance(emb, list):
                    clean_embeds.append([float(x) for x in emb])
                else:
                    clean_embeds.append(emb)
            embeddings = clean_embeds
        
        all_data[col_name] = {
            "ids": data["ids"],
            "documents": data.get("documents", []),
            "metadatas": data.get("metadatas", []),
            "embeddings": embeddings,
            "metadata": col.metadata or {},
        }
    
    output_path = os.path.join(OUTPUT_DIR, "chromadb_export.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, cls=NumpyEncoder)
    
    total = sum(len(v["ids"]) for v in all_data.values())
    print(f"Export tamamlandi: {total} kayit -> {output_path}")
    
    # Dosya boyutunu goster
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Dosya boyutu: {size_mb:.2f} MB")

if __name__ == "__main__":
    export_all()
'''

REMOTE_IMPORT_SCRIPT = r'''
#!/usr/bin/env python3
"""ChromaDB Import Helper - Server 1'e veri iceri aktar (merge)"""
import json
import sys
import os

CHROMA_DIR = "/opt/companyai/data/chromadb"
INPUT_DIR = "/tmp/companyai_sync"

def import_merge():
    input_path = os.path.join(INPUT_DIR, "chromadb_export.json")
    if not os.path.exists(input_path):
        print(f"HATA: Export dosyasi bulunamadi: {input_path}", file=sys.stderr)
        sys.exit(1)
    with open(input_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DIR)
    except Exception as e:
        print(f"HATA: ChromaDB baglanti hatasi: {e}", file=sys.stderr)
        sys.exit(1)
    total_added = 0
    total_skipped = 0
    for col_name, col_data in all_data.items():
        print(f"  Import: {col_name}")
        try:
            collection = client.get_or_create_collection(
                name=col_name, metadata=col_data.get("metadata", {}))
            existing = collection.get(include=[])
            existing_ids = set(existing["ids"]) if existing and existing.get("ids") else set()
            source_ids = col_data["ids"]
            source_docs = col_data.get("documents", [])
            source_metas = col_data.get("metadatas", [])
            source_embeds = col_data.get("embeddings", [])
            new_ids, new_docs, new_metas, new_embeds = [], [], [], []
            for i, doc_id in enumerate(source_ids):
                if doc_id not in existing_ids:
                    new_ids.append(doc_id)
                    if source_docs and i < len(source_docs):
                        new_docs.append(source_docs[i])
                    if source_metas and i < len(source_metas):
                        new_metas.append(source_metas[i])
                    if source_embeds and i < len(source_embeds):
                        emb = source_embeds[i]
                        if isinstance(emb, list):
                            emb = [float(x) for x in emb]
                        new_embeds.append(emb)
            if not new_ids:
                total_skipped += len(source_ids)
                print(f"    -> Tum kayitlar zaten mevcut ({len(existing_ids)} kayit)")
                continue
            # Ilk kayit ile dimension testi yap
            test_kw = {"ids": [new_ids[0]]}
            if new_docs: test_kw["documents"] = [new_docs[0]]
            if new_metas: test_kw["metadatas"] = [new_metas[0]]
            if new_embeds: test_kw["embeddings"] = [new_embeds[0]]
            try:
                collection.add(**test_kw)
                first_ok = True
            except Exception as e:
                err_msg = str(e)
                if "dimension" in err_msg.lower():
                    print(f"    ATLANDI: Embedding boyutu uyumsuz - {err_msg[:80]}")
                    total_skipped += len(new_ids)
                    continue
                else:
                    print(f"    HATA ilk kayit: {err_msg[:100]}")
                    total_skipped += len(new_ids)
                    continue
            # Geri kalan kayitlari ekle
            added = 1
            for j in range(1, len(new_ids)):
                try:
                    kw = {"ids": [new_ids[j]]}
                    if new_docs and j < len(new_docs):
                        kw["documents"] = [new_docs[j]]
                    if new_metas and j < len(new_metas):
                        kw["metadatas"] = [new_metas[j]]
                    if new_embeds and j < len(new_embeds):
                        kw["embeddings"] = [new_embeds[j]]
                    collection.add(**kw)
                    added += 1
                except Exception as e:
                    pass
            total_added += added
            print(f"    -> {added} yeni kayit eklendi (mevcut: {len(existing_ids)})")
        except Exception as e:
            print(f"    HATA: {col_name} import basarisiz: {str(e)[:200]}")
    print(f"\nImport tamamlandi: {total_added} eklendi, {total_skipped} atlandi")
    try:
        os.remove(input_path)
    except:
        pass

if __name__ == "__main__":
    import_merge()
'''

# ── Kullanıcı Export Script (Server 2'de çalışır) ─────────────────
REMOTE_USER_EXPORT_SCRIPT = r'''#!/usr/bin/env python3
"""PostgreSQL User Export — Sunucudan kullanici bilgilerini JSON olarak disari aktar"""
import subprocess
import json
import sys
import os
import re

OUTPUT_DIR = "/tmp/companyai_sync"

def get_db_config():
    """Veritabani bilgilerini .env dosyasindan oku"""
    env_path = "/opt/companyai/.env"
    db_user, db_pass, db_host, db_port, db_name = "companyai", "companyai", "localhost", "5432", "companyai"
    
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    url = line.strip().split("=", 1)[1]
                    # postgresql+asyncpg://user:pass@host:port/dbname
                    m = re.search(r'://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', url)
                    if m:
                        db_user, db_pass, db_host, db_port, db_name = m.groups()
    return db_user, db_pass, db_host, db_port, db_name

def export_users():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    db_user, db_pass, db_host, db_port, db_name = get_db_config()
    
    sql = """SELECT json_agg(t)::text FROM (
        SELECT email, hashed_password, full_name, department, role, 
               is_active, created_at::text, updated_at::text
        FROM users
        ORDER BY id
    ) t"""
    
    env = os.environ.copy()
    env["PGPASSWORD"] = db_pass
    
    result = subprocess.run(
        ["psql", "-h", db_host, "-p", db_port, "-U", db_user, "-d", db_name, "-t", "-A", "-c", sql],
        capture_output=True, text=True, timeout=30, env=env
    )
    
    if result.returncode != 0:
        print(f"HATA: psql hatasi: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    
    raw = result.stdout.strip()
    if not raw or raw == "":
        print("Kullanici bulunamadi")
        json.dump([], open(os.path.join(OUTPUT_DIR, "users_export.json"), "w"))
        return
    
    try:
        users = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"HATA: JSON parse hatasi: {e}", file=sys.stderr)
        sys.exit(1)
    
    output_path = os.path.join(OUTPUT_DIR, "users_export.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    
    print(f"Kullanici export tamamlandi: {len(users)} kullanici -> {output_path}")

if __name__ == "__main__":
    export_users()
'''

# ── Kullanıcı Import Script (Server 1'de çalışır) ─────────────────
REMOTE_USER_IMPORT_SCRIPT = r'''#!/usr/bin/env python3
"""PostgreSQL User Import — Sunucuya kullanici bilgilerini aktar (sadece yeni olanlar)"""
import subprocess
import json
import sys
import os
import re

INPUT_DIR = "/tmp/companyai_sync"

def get_db_config():
    """Veritabani bilgilerini .env dosyasindan oku"""
    env_path = "/opt/companyai/.env"
    db_user, db_pass, db_host, db_port, db_name = "companyai", "companyai", "localhost", "5432", "companyai"
    
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    url = line.strip().split("=", 1)[1]
                    m = re.search(r'://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', url)
                    if m:
                        db_user, db_pass, db_host, db_port, db_name = m.groups()
    return db_user, db_pass, db_host, db_port, db_name

def get_env():
    db_user, db_pass, db_host, db_port, db_name = get_db_config()
    env = os.environ.copy()
    env["PGPASSWORD"] = db_pass
    return env, db_user, db_host, db_port, db_name

def escape_sql(value):
    """SQL string icin guvenli escape"""
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"

def import_users():
    input_path = os.path.join(INPUT_DIR, "users_export.json")
    if not os.path.exists(input_path):
        print(f"HATA: Export dosyasi bulunamadi: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    with open(input_path, "r", encoding="utf-8") as f:
        users = json.load(f)
    
    if not users:
        print("Aktarilacak kullanici yok")
        return
    
    print(f"Toplam {len(users)} kullanici kontrol ediliyor...")
    
    env, db_user, db_host, db_port, db_name = get_env()
    
    # Mevcut emailleri al
    result = subprocess.run(
        ["psql", "-h", db_host, "-p", db_port, "-U", db_user, "-d", db_name, "-t", "-A", "-c",
         "SELECT email FROM users"],
        capture_output=True, text=True, timeout=30, env=env
    )
    
    existing_emails = set()
    if result.returncode == 0 and result.stdout.strip():
        existing_emails = set(result.stdout.strip().split("\n"))
    
    print(f"Server 1'de mevcut: {len(existing_emails)} kullanici")
    
    # Yeni kullanicilar icin SQL olustur
    added = 0
    skipped = 0
    sql_statements = []
    
    for user in users:
        email = user.get("email", "")
        if email in existing_emails:
            skipped += 1
            continue
        
        sql = (
            f"INSERT INTO users (email, hashed_password, full_name, department, role, is_active, created_at, updated_at) "
            f"VALUES ({escape_sql(email)}, {escape_sql(user.get('hashed_password'))}, "
            f"{escape_sql(user.get('full_name'))}, {escape_sql(user.get('department'))}, "
            f"{escape_sql(user.get('role', 'user'))}, {str(user.get('is_active', True)).lower()}, "
            f"{escape_sql(user.get('created_at'))}, {escape_sql(user.get('updated_at'))}) "
            f"ON CONFLICT (email) DO NOTHING;"
        )
        sql_statements.append(sql)
    
    if not sql_statements:
        print(f"Tum kullanicilar zaten mevcut ({skipped} atlandi)")
        return
    
    # SQL dosyasina yaz ve calistir
    sql_file = os.path.join(INPUT_DIR, "import_users.sql")
    with open(sql_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_statements))
    
    result = subprocess.run(
        ["psql", "-h", db_host, "-p", db_port, "-U", db_user, "-d", db_name, "-f", sql_file],
        capture_output=True, text=True, timeout=30, env=env
    )
    
    if result.returncode != 0:
        print(f"UYARI: Bazi INSERT'ler hatali olabilir: {result.stderr[:200]}")
    
    added = len(sql_statements)
    print(f"Kullanici import tamamlandi: {added} eklendi, {skipped} zaten mevcuttu")
    
    # Temizlik
    try:
        os.remove(input_path)
        os.remove(sql_file)
    except:
        pass

if __name__ == "__main__":
    import_users()
'''


def log(msg):
    """Zaman damgalı log"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def ssh_connect(server_cfg):
    """SSH bağlantısı oluştur"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    key_path = server_cfg.get("key_path")
    if key_path and Path(key_path).exists():
        try:
            pkey = paramiko.Ed25519Key.from_private_key_file(str(key_path))
            ssh.connect(
                server_cfg["host"], port=server_cfg["port"],
                username=server_cfg["user"], pkey=pkey, timeout=15,
                allow_agent=False, look_for_keys=False
            )
            log(f"  SSH key ile bağlanıldı → {server_cfg['name']}")
            return ssh
        except Exception:
            pass
    
    ssh.connect(
        server_cfg["host"], port=server_cfg["port"],
        username=server_cfg["user"], password=server_cfg["password"],
        timeout=15, allow_agent=False, look_for_keys=False
    )
    log(f"  Şifre ile bağlanıldı → {server_cfg['name']}")
    return ssh


def run_cmd(ssh, cmd, check=True, timeout=120):
    """Uzak komut çalıştır"""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if check and exit_code != 0:
        log(f"  ⚠️ Komut hata: {cmd[:100]} → exit {exit_code}")
        if err:
            log(f"     STDERR: {err[:300]}")
    return out, err, exit_code


def upload_script(ssh, script_content, remote_path):
    """Script'i sunucuya yükle"""
    # Geçici dosyaya yaz, SCP ile gönder
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script_content)
        local_tmp = f.name
    
    try:
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(local_tmp, remote_path)
    finally:
        os.unlink(local_tmp)


def sync_chromadb(dry_run=False):
    """ChromaDB senkronizasyon: Server 2 → Server 1"""
    log("=" * 60)
    log("  ChromaDB Senkronizasyon: Server 2 → Server 1")
    log("=" * 60)
    
    if dry_run:
        log("  🔍 DRY-RUN modu — değişiklik yapılmayacak")
    
    # ── 1. Server 2'ye bağlan ve verileri export et ────────────
    log("\n📤 Server 2'den veri export ediliyor...")
    ssh_src = ssh_connect(SOURCE_SERVER)
    
    # Geçici dizin oluştur
    run_cmd(ssh_src, f"mkdir -p {REMOTE_SYNC_DIR}")
    
    # Export script'ini yükle ve çalıştır
    upload_script(ssh_src, REMOTE_EXPORT_SCRIPT, f"{REMOTE_SYNC_DIR}/export_chromadb.py")
    
    # Backend'i durdur (ChromaDB file lock)
    log("  ⏸️ Server 2 backend durduruluyor...")
    run_cmd(ssh_src, "systemctl stop companyai-backend", check=False)
    time.sleep(2)
    
    # Export çalıştır
    python_cmd = "/opt/companyai/venv/bin/python"
    out, err, code = run_cmd(
        ssh_src,
        f"{python_cmd} {REMOTE_SYNC_DIR}/export_chromadb.py",
        timeout=300
    )
    log(f"  {out}")
    
    # Backend'i tekrar başlat
    log("  ▶️ Server 2 backend başlatılıyor...")
    run_cmd(ssh_src, "systemctl start companyai-backend", check=False)
    
    if code != 0:
        log(f"  ❌ Export başarısız: {err[:300]}")
        ssh_src.close()
        return False
    
    if dry_run:
        # Sadece istatistikleri göster
        out2, _, _ = run_cmd(ssh_src, f"wc -c {REMOTE_SYNC_DIR}/chromadb_export.json")
        log(f"  📊 Export dosyası boyutu: {out2}")
        ssh_src.close()
        log("  🔍 DRY-RUN tamamlandı")
        return True
    
    # ── 2. Export dosyasını Server 2'den indir ─────────────────
    log("\n📥 Export dosyası indiriliyor...")
    local_tmp = os.path.join(tempfile.gettempdir(), "chromadb_export.json")
    
    with SCPClient(ssh_src.get_transport()) as scp:
        scp.get(f"{REMOTE_SYNC_DIR}/chromadb_export.json", local_tmp)
    
    file_size = os.path.getsize(local_tmp) / (1024 * 1024)
    log(f"  ✅ İndirildi: {file_size:.2f} MB")
    
    # Server 2 temizlik
    run_cmd(ssh_src, f"rm -rf {REMOTE_SYNC_DIR}")
    ssh_src.close()
    
    # ── 3. Server 1'e bağlan ve verileri import et ─────────────
    log("\n📤 Server 1'e veri import ediliyor...")
    ssh_tgt = ssh_connect(TARGET_SERVER)
    
    # Geçici dizin oluştur
    run_cmd(ssh_tgt, f"mkdir -p {REMOTE_SYNC_DIR}")
    
    # Export dosyasını Server 1'e yükle
    with SCPClient(ssh_tgt.get_transport()) as scp:
        scp.put(local_tmp, f"{REMOTE_SYNC_DIR}/chromadb_export.json")
    
    # Lokal geçici dosyayı sil
    os.unlink(local_tmp)
    
    # Import script'ini yükle
    upload_script(ssh_tgt, REMOTE_IMPORT_SCRIPT, f"{REMOTE_SYNC_DIR}/import_chromadb.py")
    
    # Backend'i durdur (ChromaDB file lock)
    log("  ⏸️ Server 1 backend durduruluyor...")
    run_cmd(ssh_tgt, "systemctl stop companyai-backend", check=False)
    time.sleep(2)
    
    # Import çalıştır
    python_cmd_s1 = "python3"  # Server 1 sistem Python
    out, err, code = run_cmd(
        ssh_tgt,
        f"{python_cmd_s1} {REMOTE_SYNC_DIR}/import_chromadb.py",
        timeout=300
    )
    log(f"  {out}")
    
    # Backend'i tekrar başlat
    log("  ▶️ Server 1 backend başlatılıyor...")
    run_cmd(ssh_tgt, "systemctl start companyai-backend", check=False)
    
    # Temizlik
    run_cmd(ssh_tgt, f"rm -rf {REMOTE_SYNC_DIR}")
    ssh_tgt.close()
    
    if code != 0:
        log(f"  ❌ Import başarısız: {err[:300]}")
        return False
    
    log("\n✅ ChromaDB senkronizasyonu tamamlandı!")
    log("=" * 60)
    return True


def sync_users(dry_run=False):
    """Kullanıcı senkronizasyon: Server 2 → Server 1"""
    log("=" * 60)
    log("  Kullanıcı Senkronizasyon: Server 2 → Server 1")
    log("=" * 60)

    if dry_run:
        log("  🔍 DRY-RUN modu — değişiklik yapılmayacak")

    # ── 1. Server 2'den kullanıcıları export et ───────────────
    log("\n👤 Server 2'den kullanıcılar export ediliyor...")
    ssh_src = ssh_connect(SOURCE_SERVER)

    run_cmd(ssh_src, f"mkdir -p {REMOTE_SYNC_DIR}")
    upload_script(ssh_src, REMOTE_USER_EXPORT_SCRIPT, f"{REMOTE_SYNC_DIR}/export_users.py")

    python_cmd = "/opt/companyai/venv/bin/python"
    out, err, code = run_cmd(
        ssh_src,
        f"{python_cmd} {REMOTE_SYNC_DIR}/export_users.py",
        timeout=60
    )
    log(f"  {out}")

    if code != 0:
        log(f"  ❌ Kullanıcı export başarısız: {err[:300]}")
        ssh_src.close()
        return False

    if dry_run:
        ssh_src.close()
        log("  🔍 DRY-RUN tamamlandı")
        return True

    # ── 2. Export dosyasını indir ─────────────────────────────
    log("\n📥 Kullanıcı verisi indiriliyor...")
    local_tmp = os.path.join(tempfile.gettempdir(), "users_export.json")

    try:
        with SCPClient(ssh_src.get_transport()) as scp:
            scp.get(f"{REMOTE_SYNC_DIR}/users_export.json", local_tmp)
    except Exception as e:
        log(f"  ⚠️ Kullanıcı dosyası indirilemedi: {e}")
        ssh_src.close()
        return False

    # S2 temizlik
    run_cmd(ssh_src, f"rm -f {REMOTE_SYNC_DIR}/export_users.py {REMOTE_SYNC_DIR}/users_export.json")
    ssh_src.close()

    # Kontrol
    with open(local_tmp, "r", encoding="utf-8") as f:
        users = json.load(f)
    log(f"  ✅ {len(users)} kullanıcı export edildi")

    if not users:
        os.unlink(local_tmp)
        log("  Aktarılacak kullanıcı yok")
        return True

    # ── 3. Server 1'e import et ──────────────────────────────
    log("\n👤 Server 1'e kullanıcılar import ediliyor...")
    ssh_tgt = ssh_connect(TARGET_SERVER)

    run_cmd(ssh_tgt, f"mkdir -p {REMOTE_SYNC_DIR}")

    # Kullanıcı dosyasını Server 1'e yükle
    with SCPClient(ssh_tgt.get_transport()) as scp:
        scp.put(local_tmp, f"{REMOTE_SYNC_DIR}/users_export.json")

    os.unlink(local_tmp)

    # Import script'ini yükle
    upload_script(ssh_tgt, REMOTE_USER_IMPORT_SCRIPT, f"{REMOTE_SYNC_DIR}/import_users.py")

    # Import çalıştır
    python_cmd_s1 = "python3"
    out, err, code = run_cmd(
        ssh_tgt,
        f"{python_cmd_s1} {REMOTE_SYNC_DIR}/import_users.py",
        timeout=60
    )
    log(f"  {out}")

    # Temizlik
    run_cmd(ssh_tgt, f"rm -f {REMOTE_SYNC_DIR}/import_users.py {REMOTE_SYNC_DIR}/users_export.json {REMOTE_SYNC_DIR}/import_users.sql")
    ssh_tgt.close()

    if code != 0:
        log(f"  ⚠️ Kullanıcı import uyarı: {err[:300]}")

    log("\n✅ Kullanıcı senkronizasyonu tamamlandı!")
    log("=" * 60)
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    users_only = "--users-only" in sys.argv
    chromadb_only = "--chromadb-only" in sys.argv

    success = True

    if not users_only:
        if not sync_chromadb(dry_run=dry_run):
            success = False

    if not chromadb_only:
        if not sync_users(dry_run=dry_run):
            success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

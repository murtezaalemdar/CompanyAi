"""ChromaDB Tek Seferlik Transfer: Server 1 → Server 2

Server 1'deki ChromaDB eğitim verilerini (company_documents + company_memory)
Server 2'ye aktarır. Boyut uyumsuzluğu olan koleksiyonlarda yeniden embedding yapılır.

Kullanım:
  python transfer_s1_to_s2.py           → Aktarım başlat
  python transfer_s1_to_s2.py --dry-run → Sadece sayıları göster
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
SERVER1 = {
    "name": "server1",
    "host": "192.168.0.12",
    "port": 22,
    "user": "root",
    "password": "435102",
    "key_path": Path("keys/companyai_key"),
    "python": "python3",
}

SERVER2 = {
    "name": "server2",
    "host": "88.246.13.23",
    "port": 2013,
    "user": "root",
    "password": "Kc435102mn",
    "key_path": Path("keys/server2_key"),
    "python": "/opt/companyai/venv/bin/python",
}

CHROMA_DATA_DIR = "/opt/companyai/data/chromadb"
REMOTE_TRANSFER_DIR = "/tmp/companyai_transfer"

# ── Server 1 Export Script ────────────────────────────────────────
REMOTE_EXPORT_SCRIPT = r'''#!/usr/bin/env python3
"""ChromaDB Export — Server 1'den veri disa aktar"""
import json
import sys
import os

CHROMA_DIR = "/opt/companyai/data/chromadb"
OUTPUT_DIR = "/tmp/companyai_transfer"

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

        data = col.get(include=["documents", "metadatas", "embeddings"])

        if not data or not data.get("ids"):
            print(f"    -> Bos koleksiyon, atlaniyor")
            continue

        count = len(data["ids"])

        # Embedding boyutunu bul
        embeddings = data.get("embeddings", [])
        embed_dim = 0
        if embeddings is not None and len(embeddings) > 0:
            clean_embeds = []
            for emb in embeddings:
                if hasattr(emb, 'tolist'):
                    emb_list = emb.tolist()
                elif isinstance(emb, list):
                    emb_list = [float(x) for x in emb]
                else:
                    emb_list = emb
                clean_embeds.append(emb_list)
                if embed_dim == 0:
                    embed_dim = len(emb_list)
            embeddings = clean_embeds
        
        print(f"    -> {count} kayit, embedding dim: {embed_dim}")

        all_data[col_name] = {
            "ids": data["ids"],
            "documents": data.get("documents", []),
            "metadatas": data.get("metadatas", []),
            "embeddings": embeddings,
            "embed_dim": embed_dim,
            "metadata": col.metadata or {},
        }

    output_path = os.path.join(OUTPUT_DIR, "chromadb_export.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, cls=NumpyEncoder)

    total = sum(len(v["ids"]) for v in all_data.values())
    print(f"Export tamamlandi: {total} kayit -> {output_path}")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Dosya boyutu: {size_mb:.2f} MB")

if __name__ == "__main__":
    export_all()
'''

# ── Server 2 Import Script (re-embedding desteği) ────────────────
REMOTE_IMPORT_SCRIPT = r'''#!/usr/bin/env python3
"""ChromaDB Import — Server 2'ye veri aktar (dimension mismatch ise yeniden embedding)"""
import json
import sys
import os

CHROMA_DIR = "/opt/companyai/data/chromadb"
INPUT_DIR = "/tmp/companyai_transfer"
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

def get_embedding_model():
    """Embedding modelini yukle"""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        # Test embedding boyutu
        test = model.encode("test").tolist()
        print(f"Embedding model yuklendi, dim: {len(test)}")
        return model, len(test)
    except Exception as e:
        print(f"UYARI: Embedding model yuklenemedi: {e}")
        return None, 0

def import_to_s2():
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

    # Embedding model yukle (re-embed icin lazim olabilir)
    embed_model, target_dim = get_embedding_model()

    total_added = 0
    total_skipped = 0
    total_reembedded = 0

    for col_name, col_data in all_data.items():
        print(f"\n  Import: {col_name}")

        source_ids = col_data["ids"]
        source_docs = col_data.get("documents", [])
        source_metas = col_data.get("metadatas", [])
        source_embeds = col_data.get("embeddings", [])
        source_dim = col_data.get("embed_dim", 0)

        if not source_ids:
            print(f"    -> Bos, atlaniyor")
            continue

        # Koleksiyonu al veya olustur
        try:
            collection = client.get_or_create_collection(
                name=col_name, metadata=col_data.get("metadata", {}))
        except Exception as e:
            print(f"    HATA: Koleksiyon olusturulamadi: {e}")
            continue

        # Mevcut ID'leri al
        existing = collection.get(include=[])
        existing_ids = set(existing["ids"]) if existing and existing.get("ids") else set()
        existing_count = len(existing_ids)

        # Mevcut koleksiyonun embedding boyutunu bul
        collection_dim = 0
        if existing_count > 0:
            try:
                sample = collection.get(limit=1, include=["embeddings"])
                if sample and sample.get("embeddings") and len(sample["embeddings"]) > 0:
                    collection_dim = len(sample["embeddings"][0])
            except:
                pass

        # Boyut uyumluluğunu kontrol et
        need_reembed = False
        if source_dim > 0 and collection_dim > 0 and source_dim != collection_dim:
            need_reembed = True
            print(f"    BOYUT UYUMSUZLUGU: kaynak={source_dim}, hedef={collection_dim}")
        elif source_dim > 0 and target_dim > 0 and source_dim != target_dim and collection_dim == 0:
            need_reembed = True
            print(f"    BOYUT FARKI: kaynak={source_dim}, model={target_dim}")

        if need_reembed and not embed_model:
            print(f"    ATLANDI: Re-embed icin model yok!")
            total_skipped += len(source_ids)
            continue

        # Yeni kayitlari filtrele
        new_ids, new_docs, new_metas, new_embeds = [], [], [], []
        for i, doc_id in enumerate(source_ids):
            if doc_id not in existing_ids:
                new_ids.append(doc_id)
                if source_docs and i < len(source_docs):
                    new_docs.append(source_docs[i])
                if source_metas and i < len(source_metas):
                    new_metas.append(source_metas[i])
                if not need_reembed and source_embeds and i < len(source_embeds):
                    emb = source_embeds[i]
                    if isinstance(emb, list):
                        emb = [float(x) for x in emb]
                    new_embeds.append(emb)

        if not new_ids:
            total_skipped += len(source_ids)
            print(f"    -> Tum kayitlar zaten mevcut ({existing_count})")
            continue

        print(f"    -> {len(new_ids)} yeni kayit eklenecek (mevcut: {existing_count})")

        # Re-embed gerekiyorsa
        if need_reembed:
            print(f"    -> Yeniden embedding olusturuluyor ({len(new_ids)} kayit)...")
            new_embeds = []
            for doc in new_docs:
                if doc:
                    emb = embed_model.encode(doc).tolist()
                    new_embeds.append(emb)
                else:
                    new_embeds.append([0.0] * target_dim)
            total_reembedded += len(new_ids)
            print(f"    -> Embedding tamamlandi")

        # Batch olarak ekle
        added = 0
        batch_size = 50
        for start in range(0, len(new_ids), batch_size):
            end = min(start + batch_size, len(new_ids))
            batch_ids = new_ids[start:end]
            batch_kw = {"ids": batch_ids}

            if new_docs:
                batch_kw["documents"] = new_docs[start:end]
            if new_metas:
                batch_kw["metadatas"] = new_metas[start:end]
            if new_embeds:
                batch_kw["embeddings"] = new_embeds[start:end]

            try:
                collection.add(**batch_kw)
                added += len(batch_ids)
            except Exception as e:
                err_msg = str(e)
                if "dimension" in err_msg.lower():
                    print(f"    HATA: Batch ekleme boyut hatasi: {err_msg[:100]}")
                    # Tek tek dene
                    for j in range(start, end):
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
                        except:
                            pass
                else:
                    print(f"    HATA batch: {err_msg[:150]}")

        total_added += added
        print(f"    -> {added} kayit basariyla eklendi")

    print(f"\n{'='*50}")
    print(f"Import tamamlandi:")
    print(f"  Eklenen: {total_added}")
    print(f"  Atlanan: {total_skipped}")
    print(f"  Yeniden embed: {total_reembedded}")
    print(f"{'='*50}")

    # Temizlik
    try:
        os.remove(input_path)
    except:
        pass

if __name__ == "__main__":
    import_to_s2()
'''


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def ssh_connect(server_cfg):
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


def run_cmd(ssh, cmd, check=True, timeout=300):
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
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script_content)
        local_tmp = f.name
    try:
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(local_tmp, remote_path)
    finally:
        os.unlink(local_tmp)


def transfer_s1_to_s2(dry_run=False):
    """Server 1 ChromaDB verilerini Server 2'ye aktar"""
    log("=" * 60)
    log("  ChromaDB Transfer: Server 1 → Server 2 (tek seferlik)")
    log("=" * 60)

    if dry_run:
        log("  🔍 DRY-RUN modu — değişiklik yapılmayacak")

    # ── 1. Server 1'den export ──────────────────────────────────
    log("\n📤 Adım 1: Server 1'den ChromaDB verileri export ediliyor...")
    ssh_s1 = ssh_connect(SERVER1)

    run_cmd(ssh_s1, f"mkdir -p {REMOTE_TRANSFER_DIR}")
    upload_script(ssh_s1, REMOTE_EXPORT_SCRIPT, f"{REMOTE_TRANSFER_DIR}/export_chromadb.py")

    # Backend durdur
    log("  ⏸️ Server 1 backend durduruluyor...")
    run_cmd(ssh_s1, "systemctl stop companyai-backend", check=False)
    time.sleep(2)

    # Export çalıştır
    out, err, code = run_cmd(
        ssh_s1,
        f"{SERVER1['python']} {REMOTE_TRANSFER_DIR}/export_chromadb.py",
        timeout=600
    )
    log(f"  {out}")

    # Backend başlat
    log("  ▶️ Server 1 backend başlatılıyor...")
    run_cmd(ssh_s1, "systemctl start companyai-backend", check=False)

    if code != 0:
        log(f"  ❌ Export başarısız: {err[:300]}")
        ssh_s1.close()
        return False

    if dry_run:
        out2, _, _ = run_cmd(ssh_s1, f"wc -c {REMOTE_TRANSFER_DIR}/chromadb_export.json")
        log(f"  📊 Export boyutu: {out2}")
        run_cmd(ssh_s1, f"rm -rf {REMOTE_TRANSFER_DIR}")
        ssh_s1.close()
        log("  🔍 DRY-RUN tamamlandı")
        return True

    # ── 2. Export dosyasını indir ───────────────────────────────
    log("\n📥 Adım 2: Export dosyası Server 1'den indiriliyor...")
    local_tmp = os.path.join(tempfile.gettempdir(), "chromadb_s1_export.json")

    with SCPClient(ssh_s1.get_transport()) as scp:
        scp.get(f"{REMOTE_TRANSFER_DIR}/chromadb_export.json", local_tmp)

    file_size = os.path.getsize(local_tmp) / (1024 * 1024)
    log(f"  ✅ İndirildi: {file_size:.2f} MB")

    # S1 temizlik
    run_cmd(ssh_s1, f"rm -rf {REMOTE_TRANSFER_DIR}")
    ssh_s1.close()

    # ── 3. Server 2'ye yükle ve import et ───────────────────────
    log("\n📤 Adım 3: Server 2'ye veri import ediliyor...")
    ssh_s2 = ssh_connect(SERVER2)

    run_cmd(ssh_s2, f"mkdir -p {REMOTE_TRANSFER_DIR}")

    # Export dosyasını S2'ye yükle
    with SCPClient(ssh_s2.get_transport()) as scp:
        scp.put(local_tmp, f"{REMOTE_TRANSFER_DIR}/chromadb_export.json")

    # Lokal temizlik
    os.unlink(local_tmp)

    # Import script'ini yükle
    upload_script(ssh_s2, REMOTE_IMPORT_SCRIPT, f"{REMOTE_TRANSFER_DIR}/import_chromadb.py")

    # Backend durdur
    log("  ⏸️ Server 2 backend durduruluyor...")
    run_cmd(ssh_s2, "systemctl stop companyai-backend", check=False)
    time.sleep(2)

    # Import çalıştır (embedding model yüklemesi uzun sürebilir)
    out, err, code = run_cmd(
        ssh_s2,
        f"{SERVER2['python']} {REMOTE_TRANSFER_DIR}/import_chromadb.py",
        timeout=900
    )
    log(f"  {out}")

    # Backend başlat
    log("  ▶️ Server 2 backend başlatılıyor...")
    run_cmd(ssh_s2, "systemctl start companyai-backend", check=False)

    # Temizlik
    run_cmd(ssh_s2, f"rm -rf {REMOTE_TRANSFER_DIR}")
    ssh_s2.close()

    if code != 0:
        log(f"  ❌ Import başarısız: {err[:300]}")
        return False

    log("\n✅ Transfer tamamlandı! Server 1 verileri Server 2'ye aktarıldı.")
    log("=" * 60)
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    success = transfer_s1_to_s2(dry_run=dry_run)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

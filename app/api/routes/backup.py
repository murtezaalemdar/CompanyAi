"""Backup & Restore API Routes — Yedekleme, Zamanlama ve Geri Yükleme"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio
import json
import os
import io
import shutil
import zipfile
import tempfile
import structlog

from app.db.database import get_db, engine
from app.db.models import User, SystemSettings
from app.api.routes.auth import get_current_user
from app.auth.rbac import check_admin
from app.core.audit import log_action
from app.config import settings
from app.auth.jwt_handler import verify_token

logger = structlog.get_logger()
router = APIRouter()

# ── Backup dizini ─────────────────────────────────────────────
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/opt/companyai/backups")
SCHEDULE_FILE = os.path.join(BACKUP_DIR, ".schedule.json")
MAX_BACKUPS = 20  # Eski yedekleri otomatik temizle

# ChromaDB veri dizini (RAG belgeleri + AI hafızası)
CHROMADB_DATA_DIR = os.environ.get("CHROMA_PERSIST_DIR", "/opt/companyai/data/chromadb")


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


# ── Pydantic Models ──────────────────────────────────────────

class BackupInfo(BaseModel):
    filename: str
    size_mb: float
    created_at: str
    tables: List[str]
    note: Optional[str] = None

class ScheduleRequest(BaseModel):
    enabled: bool
    frequency: str = "daily"       # daily | weekly | monthly
    time: str = "03:00"            # HH:MM (24h)
    day_of_week: Optional[int] = 0  # 0=Pazartesi (for weekly)
    day_of_month: Optional[int] = 1 # (for monthly)
    max_keep: int = 10
    note: Optional[str] = None

class RestoreRequest(BaseModel):
    filename: str
    confirm: bool = False


# ── Yardımcı Fonksiyonlar ────────────────────────────────────

BACKUP_TABLES = [
    "users", "queries", "audit_logs", "system_settings",
    "chat_sessions", "conversation_memory",
    "user_preferences", "company_culture",
]


async def _export_table(db: AsyncSession, table_name: str) -> list:
    """Bir tabloyu dict listesine dönüştür."""
    try:
        result = await db.execute(text(f"SELECT * FROM {table_name}"))
        columns = list(result.keys())
        rows = []
        for row in result.fetchall():
            row_dict = {}
            for i, col in enumerate(columns):
                val = row[i]
                if isinstance(val, datetime):
                    val = val.isoformat()
                elif isinstance(val, (bytes, bytearray)):
                    import base64
                    val = base64.b64encode(val).decode()
                row_dict[col] = val
            rows.append(row_dict)
        return rows
    except Exception as e:
        logger.warning("table_export_failed", table=table_name, error=str(e))
        return []


async def _import_table(db: AsyncSession, table_name: str, rows: list):
    """Bir tabloyu geri yükle — önce temizle, sonra ekle."""
    if not rows:
        return 0

    # Tabloyu temizle (CASCADE ile)
    await db.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))

    # Satırları ekle
    columns = list(rows[0].keys())
    inserted = 0
    for row in rows:
        col_names = ", ".join(columns)
        placeholders = ", ".join([f":col_{i}" for i in range(len(columns))])
        params = {f"col_{i}": row[col] for i, col in enumerate(columns)}
        try:
            await db.execute(
                text(f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"),
                params
            )
            inserted += 1
        except Exception as e:
            logger.warning("row_insert_failed", table=table_name, error=str(e))
            continue

    # Sequence'leri güncelle (id sütunu varsa)
    if "id" in columns:
        try:
            await db.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table_name}), 1))"
            ))
        except Exception:
            pass

    return inserted


def _get_backup_meta(filepath: str) -> Optional[dict]:
    """Bir yedek dosyasından meta bilgi oku."""
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            if 'meta.json' in zf.namelist():
                meta = json.loads(zf.read('meta.json'))
                stat = os.stat(filepath)
                meta['size_mb'] = round(stat.st_size / (1024 * 1024), 2)
                meta['filename'] = os.path.basename(filepath)
                return meta
    except Exception:
        pass
    # Fallback
    try:
        stat = os.stat(filepath)
        return {
            "filename": os.path.basename(filepath),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "tables": [],
            "note": None,
        }
    except Exception:
        return None


def _load_schedule() -> dict:
    """Zamanlama ayarlarını oku."""
    default = {
        "enabled": False,
        "frequency": "daily",
        "time": "03:00",
        "day_of_week": 0,
        "day_of_month": 1,
        "max_keep": 10,
        "note": None,
        "last_run": None,
        "next_run": None,
    }
    try:
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, 'r') as f:
                data = json.load(f)
                default.update(data)
    except Exception:
        pass
    return default


def _save_schedule(data: dict):
    """Zamanlama ayarlarını kaydet."""
    _ensure_backup_dir()
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _calc_next_run(schedule: dict) -> Optional[str]:
    """Bir sonraki çalışma zamanını hesapla."""
    if not schedule.get("enabled"):
        return None

    now = datetime.now()
    hour, minute = map(int, schedule.get("time", "03:00").split(":"))
    freq = schedule.get("frequency", "daily")

    if freq == "daily":
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
    elif freq == "weekly":
        dow = schedule.get("day_of_week", 0)
        days_ahead = (dow - now.weekday()) % 7
        next_run = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(weeks=1)
    elif freq == "monthly":
        dom = schedule.get("day_of_month", 1)
        next_run = now.replace(day=min(dom, 28), hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            month = now.month + 1
            year = now.year
            if month > 12:
                month = 1
                year += 1
            next_run = next_run.replace(year=year, month=month)
    else:
        return None

    return next_run.isoformat()


def _cleanup_old_backups(max_keep: int = MAX_BACKUPS):
    """Eski yedekleri temizle (en yenileri koru)."""
    _ensure_backup_dir()
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith('.zip')],
        key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)),
        reverse=True
    )
    for old_file in backups[max_keep:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old_file))
            logger.info("old_backup_removed", file=old_file)
        except Exception:
            pass


# ── API Endpoints ─────────────────────────────────────────────

@router.get("/list")
async def list_backups(
    current_user: User = Depends(get_current_user),
):
    """Mevcut yedek dosyalarını listele."""
    check_admin(current_user)
    _ensure_backup_dir()

    backups = []
    for fname in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if not fname.endswith('.zip'):
            continue
        filepath = os.path.join(BACKUP_DIR, fname)
        meta = _get_backup_meta(filepath)
        if meta:
            backups.append(meta)

    return {"backups": backups, "backup_dir": BACKUP_DIR}


@router.post("/create")
async def create_backup(
    note: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manuel yedek oluştur — tüm tabloları ZIP'e kaydet."""
    check_admin(current_user)
    _ensure_backup_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"companyai_backup_{timestamp}.zip"
    filepath = os.path.join(BACKUP_DIR, filename)

    # Tüm tabloları export et
    table_data = {}
    table_counts = {}
    for table in BACKUP_TABLES:
        rows = await _export_table(db, table)
        table_data[table] = rows
        table_counts[table] = len(rows)

    # Meta bilgi
    meta = {
        "version": settings.APP_VERSION if hasattr(settings, 'APP_VERSION') else "unknown",
        "created_at": datetime.now().isoformat(),
        "created_by": current_user.email,
        "tables": list(table_data.keys()),
        "row_counts": table_counts,
        "note": note or f"Manuel yedek — {current_user.full_name or current_user.email}",
        "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "***",
    }

    # ChromaDB verilerini hazırla
    chromadb_included = False
    chromadb_size = 0
    if os.path.isdir(CHROMADB_DATA_DIR):
        chromadb_included = True
        for root, dirs, files in os.walk(CHROMADB_DATA_DIR):
            for f in files:
                chromadb_size += os.path.getsize(os.path.join(root, f))

    meta["chromadb_included"] = chromadb_included
    meta["chromadb_size_mb"] = round(chromadb_size / (1024 * 1024), 2)

    # ZIP oluştur
    with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('meta.json', json.dumps(meta, ensure_ascii=False, indent=2, default=str))
        for table, rows in table_data.items():
            zf.writestr(f'tables/{table}.json', json.dumps(rows, ensure_ascii=False, indent=2, default=str))

        # ChromaDB dosyalarını ekle
        if chromadb_included:
            for root, dirs, files in os.walk(CHROMADB_DATA_DIR):
                for f in files:
                    full_path = os.path.join(root, f)
                    arc_path = os.path.relpath(full_path, CHROMADB_DATA_DIR)
                    zf.write(full_path, f'chromadb/{arc_path}')

    # Eski yedekleri temizle
    _cleanup_old_backups()

    stat = os.stat(filepath)
    await log_action(db, user_id=current_user.id, action="backup_created", resource="backup", details=f"Yedek: {filename}")

    logger.info("backup_created", filename=filename, tables=len(table_data),
                total_rows=sum(table_counts.values()), chromadb=chromadb_included)

    return {
        "status": "success",
        "filename": filename,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "tables": list(table_data.keys()),
        "row_counts": table_counts,
        "total_rows": sum(table_counts.values()),
        "chromadb_included": chromadb_included,
        "chromadb_size_mb": meta.get("chromadb_size_mb", 0),
        "note": meta["note"],
    }


@router.get("/download/{filename}")
async def download_backup(
    filename: str,
    token: Optional[str] = Query(None, description="JWT token for browser download"),
    db: AsyncSession = Depends(get_db),
):
    """Yedek dosyasını indir (browser'dan token query param ile)."""
    if not token:
        raise HTTPException(status_code=401, detail="Token gerekli")

    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Geçersiz token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Geçersiz token")

    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == int(user_id)))
    current_user = result.scalar_one_or_none()

    if current_user is None:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")

    check_admin(current_user)

    # Güvenlik: sadece dosya adı kabul et
    safe_name = os.path.basename(filename)
    filepath = os.path.join(BACKUP_DIR, safe_name)

    if not os.path.exists(filepath) or not safe_name.endswith('.zip'):
        raise HTTPException(status_code=404, detail="Yedek dosyası bulunamadı")

    file_size = os.path.getsize(filepath)

    def iterfile():
        with open(filepath, 'rb') as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={safe_name}",
            "Content-Length": str(file_size),
        }
    )


@router.post("/restore")
async def restore_backup(
    req: RestoreRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yedekten geri yükle — DİKKAT: Mevcut veriler silinir!"""
    check_admin(current_user)

    if not req.confirm:
        raise HTTPException(
            status_code=400,
            detail="Geri yükleme onaylanmadı. confirm=true gönderin. ⚠️ Mevcut tüm veriler silinecek!"
        )

    safe_name = os.path.basename(req.filename)
    filepath = os.path.join(BACKUP_DIR, safe_name)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Yedek dosyası bulunamadı")

    # ZIP'ten verileri oku
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            meta = json.loads(zf.read('meta.json'))
            restore_results = {}

            # Doğru sırayla geri yükle (foreign key bağımlılıkları)
            ordered_tables = [
                "users", "system_settings", "chat_sessions",
                "queries", "audit_logs", "conversation_memory",
                "user_preferences", "company_culture",
            ]

            for table in ordered_tables:
                table_file = f'tables/{table}.json'
                if table_file in zf.namelist():
                    rows = json.loads(zf.read(table_file))
                    count = await _import_table(db, table, rows)
                    restore_results[table] = {"restored": count, "total": len(rows)}
                else:
                    restore_results[table] = {"restored": 0, "total": 0, "skipped": True}

            await db.commit()

            # ChromaDB geri yükle
            chromadb_files = [n for n in zf.namelist() if n.startswith('chromadb/')]
            chromadb_restored = False
            if chromadb_files:
                # Mevcut ChromaDB'yi temizle ve yedekten yükle
                if os.path.isdir(CHROMADB_DATA_DIR):
                    shutil.rmtree(CHROMADB_DATA_DIR)
                os.makedirs(CHROMADB_DATA_DIR, exist_ok=True)
                for arc_path in chromadb_files:
                    rel_path = arc_path[len('chromadb/'):]
                    if not rel_path:  # dizin girişi
                        continue
                    target = os.path.join(CHROMADB_DATA_DIR, rel_path)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with zf.open(arc_path) as src, open(target, 'wb') as dst:
                        dst.write(src.read())
                chromadb_restored = True
                logger.info("chromadb_restored", files=len(chromadb_files))
            restore_results["chromadb"] = {"restored": chromadb_restored, "files": len(chromadb_files)}

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Geçersiz yedek dosyası")
    except Exception as e:
        await db.rollback()
        logger.error("restore_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Geri yükleme hatası: {str(e)}")

    await log_action(db, user_id=current_user.id, action="backup_restored", resource="backup", details=f"Geri yükleme: {safe_name}")

    logger.info("backup_restored", filename=safe_name, results=restore_results)

    return {
        "status": "success",
        "restored_from": safe_name,
        "backup_date": meta.get("created_at"),
        "results": restore_results,
    }


@router.delete("/delete/{filename}")
async def delete_backup(
    filename: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yedek dosyasını sil."""
    check_admin(current_user)

    safe_name = os.path.basename(filename)
    filepath = os.path.join(BACKUP_DIR, safe_name)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Yedek dosyası bulunamadı")

    os.remove(filepath)
    await log_action(db, user_id=current_user.id, action="backup_deleted", resource="backup", details=f"Silindi: {safe_name}")

    return {"status": "success", "deleted": safe_name}


@router.post("/upload")
async def upload_backup(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Harici yedek dosyası yükle."""
    check_admin(current_user)
    _ensure_backup_dir()

    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Sadece .zip formatı desteklenir")

    content = await file.read()

    # ZIP geçerliliğini kontrol et
    try:
        with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
            if 'meta.json' not in zf.namelist():
                raise HTTPException(status_code=400, detail="Geçersiz yedek formatı: meta.json bulunamadı")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Geçersiz ZIP dosyası")

    # Kaydet
    safe_name = os.path.basename(file.filename)
    filepath = os.path.join(BACKUP_DIR, safe_name)
    with open(filepath, 'wb') as f:
        f.write(content)

    meta = _get_backup_meta(filepath)
    return {"status": "success", "filename": safe_name, "meta": meta}


# ── Zamanlama Endpoints ──────────────────────────────────────

@router.get("/schedule")
async def get_schedule(
    current_user: User = Depends(get_current_user),
):
    """Mevcut yedekleme zamanlamasını getir."""
    check_admin(current_user)
    schedule = _load_schedule()
    schedule["next_run"] = _calc_next_run(schedule)
    return schedule


@router.put("/schedule")
async def update_schedule(
    req: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yedekleme zamanlamasını güncelle."""
    check_admin(current_user)

    schedule = _load_schedule()
    schedule.update(req.dict())
    schedule["next_run"] = _calc_next_run(schedule)
    schedule["updated_by"] = current_user.email
    schedule["updated_at"] = datetime.now().isoformat()
    _save_schedule(schedule)

    await log_action(db, user_id=current_user.id, action="backup_schedule_updated", resource="backup",
                     details=f"Zamanlama: {req.frequency} @ {req.time}, aktif={req.enabled}")

    return {"status": "success", "schedule": schedule}


@router.get("/info")
async def backup_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yedekleme sistemi genel bilgi — tablo boyutları, disk kullanımı."""
    check_admin(current_user)
    _ensure_backup_dir()

    # Tablo satır sayıları
    table_stats = {}
    for table in BACKUP_TABLES:
        try:
            result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            table_stats[table] = count
        except Exception:
            table_stats[table] = -1

    # Disk kullanımı
    backup_files = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.zip')]
    total_size = sum(
        os.path.getsize(os.path.join(BACKUP_DIR, f))
        for f in backup_files
    )

    # Veritabanı boyutu
    try:
        result = await db.execute(text("SELECT pg_database_size(current_database())"))
        db_size = result.scalar()
    except Exception:
        db_size = 0

    # ChromaDB boyutu
    chromadb_size = 0
    chromadb_exists = os.path.isdir(CHROMADB_DATA_DIR)
    if chromadb_exists:
        for root, dirs, files in os.walk(CHROMADB_DATA_DIR):
            for f in files:
                chromadb_size += os.path.getsize(os.path.join(root, f))

    schedule = _load_schedule()

    return {
        "table_stats": table_stats,
        "total_rows": sum(v for v in table_stats.values() if v > 0),
        "backup_count": len(backup_files),
        "backup_total_size_mb": round(total_size / (1024 * 1024), 2),
        "database_size_mb": round((db_size or 0) / (1024 * 1024), 2),
        "chromadb_size_mb": round(chromadb_size / (1024 * 1024), 2),
        "chromadb_available": chromadb_exists,
        "backup_dir": BACKUP_DIR,
        "max_backups": MAX_BACKUPS,
        "schedule_enabled": schedule.get("enabled", False),
        "schedule_next_run": _calc_next_run(schedule),
    }

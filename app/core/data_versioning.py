"""Data Versioning — Veri Seti Değişiklik Takibi, Snapshot ve Rollback

Özellikleri:
- Dataset değişiklik takibi (hash, satır/sütun sayısı)
- Snapshot alma ve geri yükleme (rollback)
- Sürümler arası diff (fark) analizi
- RAG ve ChromaDB koleksiyonları için versiyon takibi
"""

import json
import hashlib
import shutil
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path
import structlog

logger = structlog.get_logger()

_VERSIONS_DIR = Path("data/data_versions")
_VERSION_INDEX = Path("data/data_version_index.json")


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_hash(path: Path) -> str:
    """SHA-256 dosya hash'i."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_stats(path: Path) -> Dict:
    """Dosya istatistikleri."""
    stat = path.stat()
    info = {
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # CSV/JSON satır sayısı
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            with open(path, "r", encoding="utf-8") as f:
                lines = sum(1 for _ in f)
            info["row_count"] = lines - 1  # header hariç
            with open(path, "r", encoding="utf-8") as f:
                header = f.readline().strip()
            info["columns"] = header.split(",")
            info["column_count"] = len(info["columns"])
        elif suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                info["row_count"] = len(data)
                if data:
                    info["columns"] = list(data[0].keys()) if isinstance(data[0], dict) else []
                    info["column_count"] = len(info.get("columns", []))
            elif isinstance(data, dict):
                info["key_count"] = len(data)
        elif suffix == ".jsonl":
            with open(path, "r", encoding="utf-8") as f:
                lines = sum(1 for _ in f)
            info["row_count"] = lines
    except Exception:
        pass

    return info


class DataVersionManager:
    """Veri seti versiyon yöneticisi."""

    def __init__(self):
        _VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._index = self._load_index()

    def _load_index(self) -> Dict:
        if _VERSION_INDEX.exists():
            try:
                return json.loads(_VERSION_INDEX.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"datasets": {}, "created_at": _utcnow_str()}

    def _save_index(self):
        _VERSION_INDEX.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def create_snapshot(
        self,
        file_path: str,
        dataset_name: Optional[str] = None,
        description: str = "",
        created_by: str = "system",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Bir dosyanın snapshot'ını al."""
        source = Path(file_path)
        if not source.exists():
            raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")

        ds_name = dataset_name or source.stem
        file_hash = _file_hash(source)

        # Aynı hash zaten var mı kontrol et
        if ds_name in self._index["datasets"]:
            versions = self._index["datasets"][ds_name].get("versions", [])
            for v in versions:
                if v.get("hash") == file_hash:
                    logger.info("snapshot_skipped_duplicate", dataset=ds_name, hash=file_hash[:12])
                    return {**v, "skipped": True, "reason": "Aynı içerik zaten versiyonlanmış"}

        # Versiyon numarası
        if ds_name not in self._index["datasets"]:
            self._index["datasets"][ds_name] = {"versions": [], "created_at": _utcnow_str()}
        version_num = len(self._index["datasets"][ds_name]["versions"]) + 1
        version_tag = f"v{version_num}"

        # Dosyayı kopyala
        snapshot_dir = _VERSIONS_DIR / ds_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshot_dir / f"{version_tag}_{source.name}"
        shutil.copy2(str(source), str(snapshot_file))

        # Metadata
        stats = _file_stats(source)
        version_entry = {
            "version": version_tag,
            "version_num": version_num,
            "hash": file_hash,
            "original_path": str(source),
            "snapshot_path": str(snapshot_file),
            "description": description,
            "created_by": created_by,
            "created_at": _utcnow_str(),
            "tags": tags or [],
            "stats": stats,
        }

        self._index["datasets"][ds_name]["versions"].append(version_entry)
        self._index["datasets"][ds_name]["latest_version"] = version_tag
        self._index["datasets"][ds_name]["latest_hash"] = file_hash
        self._save_index()

        logger.info("snapshot_created", dataset=ds_name, version=version_tag, hash=file_hash[:12])
        return version_entry

    def rollback(
        self,
        dataset_name: str,
        target_version: str,
        rolled_back_by: str = "system",
    ) -> Dict[str, Any]:
        """Bir veri setini belirli bir versiyona geri yükle."""
        ds = self._index["datasets"].get(dataset_name)
        if not ds:
            raise KeyError(f"Dataset bulunamadı: {dataset_name}")

        target = None
        for v in ds["versions"]:
            if v["version"] == target_version:
                target = v
                break
        if not target:
            raise KeyError(f"Versiyon bulunamadı: {target_version}")

        snapshot_path = Path(target["snapshot_path"])
        original_path = Path(target["original_path"])

        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot dosyası bulunamadı: {snapshot_path}")

        # Mevcut dosyanın yedeğini al
        if original_path.exists():
            current_hash = _file_hash(original_path)
            if current_hash != target["hash"]:
                # Otomatik snapshot al (mevcut durumu kaybet)
                self.create_snapshot(
                    str(original_path),
                    dataset_name,
                    f"Rollback öncesi otomatik yedek ({target_version}'e dönülecek)",
                    rolled_back_by,
                    tags=["auto_backup", "pre_rollback"],
                )

        # Geri yükle
        shutil.copy2(str(snapshot_path), str(original_path))

        rollback_entry = {
            "action": "rollback",
            "target_version": target_version,
            "rolled_back_by": rolled_back_by,
            "timestamp": _utcnow_str(),
        }

        logger.info("dataset_rolled_back", dataset=dataset_name, to_version=target_version)
        return {**target, "rollback": rollback_entry}

    def diff(self, dataset_name: str, version_a: str, version_b: str) -> Dict:
        """İki versiyon arasındaki farkı göster (metadata bazlı)."""
        ds = self._index["datasets"].get(dataset_name)
        if not ds:
            raise KeyError(f"Dataset bulunamadı: {dataset_name}")

        va = vb = None
        for v in ds["versions"]:
            if v["version"] == version_a:
                va = v
            if v["version"] == version_b:
                vb = v

        if not va or not vb:
            raise KeyError("Versiyonlardan biri bulunamadı")

        sa = va.get("stats", {})
        sb = vb.get("stats", {})

        diff_result = {
            "dataset": dataset_name,
            "version_a": version_a,
            "version_b": version_b,
            "same_content": va["hash"] == vb["hash"],
            "size_change_mb": round(sb.get("size_mb", 0) - sa.get("size_mb", 0), 2),
            "row_change": (sb.get("row_count", 0) or 0) - (sa.get("row_count", 0) or 0),
        }

        # Sütun değişiklikleri
        cols_a = set(sa.get("columns", []))
        cols_b = set(sb.get("columns", []))
        if cols_a or cols_b:
            diff_result["columns_added"] = sorted(cols_b - cols_a)
            diff_result["columns_removed"] = sorted(cols_a - cols_b)
            diff_result["columns_unchanged"] = sorted(cols_a & cols_b)

        return diff_result

    def list_datasets(self) -> List[Dict]:
        """Tüm veri setlerini listele."""
        result = []
        for name, ds in self._index.get("datasets", {}).items():
            versions = ds.get("versions", [])
            result.append({
                "name": name,
                "total_versions": len(versions),
                "latest_version": ds.get("latest_version"),
                "created_at": ds.get("created_at"),
                "latest_stats": versions[-1].get("stats", {}) if versions else {},
            })
        return result

    def get_versions(self, dataset_name: str) -> List[Dict]:
        """Bir veri setinin tüm versiyonlarını listele."""
        ds = self._index["datasets"].get(dataset_name)
        if not ds:
            raise KeyError(f"Dataset bulunamadı: {dataset_name}")
        return ds.get("versions", [])

    def check_changes(self, file_path: str, dataset_name: Optional[str] = None) -> Dict:
        """Bir dosyanın son snapshot'tan bu yana değişip değişmediğini kontrol et."""
        source = Path(file_path)
        if not source.exists():
            return {"exists": False, "error": f"Dosya bulunamadı: {file_path}"}

        ds_name = dataset_name or source.stem
        current_hash = _file_hash(source)
        current_stats = _file_stats(source)

        ds = self._index["datasets"].get(ds_name)
        if not ds or not ds.get("versions"):
            return {
                "dataset": ds_name,
                "has_versions": False,
                "changed": True,
                "current_hash": current_hash[:12],
                "current_stats": current_stats,
            }

        latest = ds["versions"][-1]
        changed = latest["hash"] != current_hash

        return {
            "dataset": ds_name,
            "has_versions": True,
            "changed": changed,
            "current_hash": current_hash[:12],
            "latest_version": latest["version"],
            "latest_hash": latest["hash"][:12],
            "current_stats": current_stats,
            "latest_stats": latest.get("stats", {}),
        }

    def get_dashboard(self) -> Dict:
        """Data versioning dashboard özeti."""
        datasets = self._index.get("datasets", {})
        total_versions = sum(len(ds.get("versions", [])) for ds in datasets.values())
        total_size_mb = 0
        for ds in datasets.values():
            for v in ds.get("versions", []):
                total_size_mb += v.get("stats", {}).get("size_mb", 0)

        return {
            "total_datasets": len(datasets),
            "total_versions": total_versions,
            "total_snapshot_size_mb": round(total_size_mb, 2),
            "datasets": self.list_datasets(),
        }


# Singleton instance
data_version_manager = DataVersionManager()

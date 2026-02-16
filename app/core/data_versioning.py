"""Data Versioning — Veri Seti Değişiklik Takibi, Snapshot ve Rollback

Snapshot, rollback, içerik-seviye diff, lineage, retention, gzip sıkıştırma,
SHA-256 bütünlük doğrulaması, operasyon günlüğü, bulk snapshot, depolama
analitikleri ve dashboard sağlar.
"""

import csv
import gzip
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    """Dosya istatistikleri (boyut, satır/sütun sayısı)."""
    stat = path.stat()
    info: Dict[str, Any] = {
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            with open(path, "r", encoding="utf-8") as f:
                lines = sum(1 for _ in f)
            info["row_count"] = lines - 1
            with open(path, "r", encoding="utf-8") as f:
                header = f.readline().strip()
            info["columns"] = header.split(",")
            info["column_count"] = len(info["columns"])
        elif suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                info["row_count"] = len(data)
                if data and isinstance(data[0], dict):
                    info["columns"] = list(data[0].keys())
                    info["column_count"] = len(info["columns"])
            elif isinstance(data, dict):
                info["key_count"] = len(data)
        elif suffix == ".jsonl":
            with open(path, "r", encoding="utf-8") as f:
                info["row_count"] = sum(1 for _ in f)
    except Exception:
        pass
    return info


def _read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    """CSV dosyasını oku → (başlıklar, satır_dict_listesi)."""
    rows: List[Dict[str, str]] = []
    headers: List[str] = []
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            headers = list(reader.fieldnames or [])
            for row in reader:
                rows.append(dict(row))
    except Exception:
        pass
    return headers, rows


def _read_json_data(path: Path) -> Any:
    """JSON dosyasını parse et."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


class DataVersionManager:
    """Veri seti versiyon yöneticisi — snapshot, rollback, diff, lineage, retention."""

    def __init__(self) -> None:
        _VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._index = self._load_index()
        # İstatistik takipçi
        self._stats: Dict[str, Any] = {
            "total_snapshots": 0, "total_rollbacks": 0, "total_diffs": 0,
            "total_compressions": 0, "total_verifications": 0,
            "datasets_tracked": 0, "storage_bytes": 0,
        }
        self._operation_log: List[Dict[str, Any]] = []   # bellek-içi günlük
        self._retention_policies: Dict[str, int] = {}     # dataset → max_versions
        self._refresh_stats()

    # ── Dahili yardımcılar ─────────────────────────────────────────

    def _load_index(self) -> Dict:
        if _VERSION_INDEX.exists():
            try:
                return json.loads(_VERSION_INDEX.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"datasets": {}, "created_at": _utcnow_str()}

    def _save_index(self) -> None:
        _VERSION_INDEX.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _log_op(self, operation: str, **details: Any) -> None:
        """Operasyon günlüğüne kayıt ekle (son 500)."""
        self._operation_log.append({"operation": operation, "timestamp": _utcnow_str(), **details})
        if len(self._operation_log) > 500:
            self._operation_log = self._operation_log[-500:]

    def _refresh_stats(self) -> None:
        """İndeksten istatistikleri yenile."""
        datasets = self._index.get("datasets", {})
        self._stats["datasets_tracked"] = len(datasets)
        total_bytes = total_snaps = 0
        for ds in datasets.values():
            versions = ds.get("versions", [])
            total_snaps += len(versions)
            for v in versions:
                total_bytes += v.get("stats", {}).get("size_bytes", 0)
        self._stats["storage_bytes"] = total_bytes
        if self._stats["total_snapshots"] == 0:
            self._stats["total_snapshots"] = total_snaps

    def _apply_retention(self, dataset_name: str) -> List[Dict]:
        """Retention politikasını uygula, silinen versiyonları döndür."""
        max_v = self._retention_policies.get(dataset_name)
        if max_v is None:
            return []
        ds = self._index["datasets"].get(dataset_name)
        if not ds:
            return []
        versions = ds.get("versions", [])
        if len(versions) <= max_v:
            return []
        to_remove = versions[: len(versions) - max_v]
        removed: List[Dict] = []
        for v in to_remove:
            snap = Path(v.get("snapshot_path", ""))
            if snap.exists():
                try:
                    snap.unlink()
                except OSError:
                    pass
            gz = Path(str(snap) + ".gz")
            if gz.exists():
                try:
                    gz.unlink()
                except OSError:
                    pass
            removed.append(v)
        ds["versions"] = versions[len(versions) - max_v :]
        self._save_index()
        self._log_op("retention_cleanup", dataset=dataset_name, removed_count=len(removed))
        return removed

    def _find_version(self, ds: Dict, ver: str) -> Optional[Dict]:
        """Versiyon kaydını bul."""
        for v in ds.get("versions", []):
            if v["version"] == ver:
                return v
        return None

    # ── Snapshot ────────────────────────────────────────────────────

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
        hash_val = _file_hash(source)

        # Tekrar kontrolü
        if ds_name in self._index["datasets"]:
            for v in self._index["datasets"][ds_name].get("versions", []):
                if v.get("hash") == hash_val:
                    logger.info("snapshot_skipped_duplicate", dataset=ds_name, hash=hash_val[:12])
                    return {**v, "skipped": True, "reason": "Aynı içerik zaten versiyonlanmış"}

        # Yeni dataset kaydı
        if ds_name not in self._index["datasets"]:
            self._index["datasets"][ds_name] = {"versions": [], "created_at": _utcnow_str(), "lineage": []}

        vlist = self._index["datasets"][ds_name]["versions"]
        vnum = len(vlist) + 1
        vtag = f"v{vnum}"
        parent = vlist[-1]["version"] if vlist else None

        # Dosyayı kopyala
        snap_dir = _VERSIONS_DIR / ds_name
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_file = snap_dir / f"{vtag}_{source.name}"
        shutil.copy2(str(source), str(snap_file))

        stats = _file_stats(source)
        entry: Dict[str, Any] = {
            "version": vtag, "version_num": vnum, "hash": hash_val,
            "original_path": str(source), "snapshot_path": str(snap_file),
            "description": description, "created_by": created_by,
            "created_at": _utcnow_str(), "tags": tags or [], "stats": stats,
            "parent_version": parent, "compressed": False,
        }
        vlist.append(entry)
        self._index["datasets"][ds_name]["latest_version"] = vtag
        self._index["datasets"][ds_name]["latest_hash"] = hash_val

        # Lineage
        if "lineage" not in self._index["datasets"][ds_name]:
            self._index["datasets"][ds_name]["lineage"] = []
        self._index["datasets"][ds_name]["lineage"].append(
            {"child": vtag, "parent": parent, "created_at": entry["created_at"]}
        )
        self._save_index()

        self._stats["total_snapshots"] += 1
        self._refresh_stats()
        self._log_op("create_snapshot", dataset=ds_name, version=vtag, hash=hash_val[:12])
        logger.info("snapshot_created", dataset=ds_name, version=vtag, hash=hash_val[:12])

        self._apply_retention(ds_name)
        return entry

    # ── Rollback ───────────────────────────────────────────────────

    def rollback(
        self,
        dataset_name: str,
        target_version: str,
        rolled_back_by: str = "system",
    ) -> Dict[str, Any]:
        """Veri setini belirli versiyona geri yükle (SHA-256 bütünlük kontrolü ile)."""
        ds = self._index["datasets"].get(dataset_name)
        if not ds:
            raise KeyError(f"Dataset bulunamadı: {dataset_name}")
        target = self._find_version(ds, target_version)
        if not target:
            raise KeyError(f"Versiyon bulunamadı: {target_version}")

        snap_path = Path(target["snapshot_path"])
        orig_path = Path(target["original_path"])
        if not snap_path.exists():
            raise FileNotFoundError(f"Snapshot dosyası bulunamadı: {snap_path}")

        # Bütünlük doğrulaması
        actual_hash = _file_hash(snap_path)
        if actual_hash != target["hash"]:
            self._log_op("integrity_check_failed", dataset=dataset_name, version=target_version)
            raise ValueError(
                f"Bütünlük hatası: Beklenen {target['hash'][:12]}, Gerçek {actual_hash[:12]}"
            )

        # Mevcut dosyanın otomatik yedeği
        if orig_path.exists():
            if _file_hash(orig_path) != target["hash"]:
                self.create_snapshot(
                    str(orig_path), dataset_name,
                    f"Rollback öncesi otomatik yedek ({target_version}'e dönülecek)",
                    rolled_back_by, tags=["auto_backup", "pre_rollback"],
                )

        shutil.copy2(str(snap_path), str(orig_path))
        self._stats["total_rollbacks"] += 1
        rollback_info = {
            "action": "rollback", "target_version": target_version,
            "rolled_back_by": rolled_back_by, "timestamp": _utcnow_str(),
            "integrity_verified": True,
        }
        self._log_op("rollback", dataset=dataset_name, target_version=target_version)
        logger.info("dataset_rolled_back", dataset=dataset_name, to_version=target_version)
        return {**target, "rollback": rollback_info}

    # ── Diff ───────────────────────────────────────────────────────

    def diff(self, dataset_name: str, version_a: str, version_b: str) -> Dict:
        """İki versiyon arasındaki farkı göster (metadata + içerik seviyesinde)."""
        ds = self._index["datasets"].get(dataset_name)
        if not ds:
            raise KeyError(f"Dataset bulunamadı: {dataset_name}")

        va = self._find_version(ds, version_a)
        vb = self._find_version(ds, version_b)
        if not va or not vb:
            raise KeyError("Versiyonlardan biri bulunamadı")

        sa, sb = va.get("stats", {}), vb.get("stats", {})
        result: Dict[str, Any] = {
            "dataset": dataset_name, "version_a": version_a, "version_b": version_b,
            "same_content": va["hash"] == vb["hash"],
            "size_change_mb": round(sb.get("size_mb", 0) - sa.get("size_mb", 0), 2),
            "row_change": (sb.get("row_count", 0) or 0) - (sa.get("row_count", 0) or 0),
        }
        # Sütun değişiklikleri
        cols_a, cols_b = set(sa.get("columns", [])), set(sb.get("columns", []))
        if cols_a or cols_b:
            result["columns_added"] = sorted(cols_b - cols_a)
            result["columns_removed"] = sorted(cols_a - cols_b)
            result["columns_unchanged"] = sorted(cols_a & cols_b)

        # İçerik düzeyinde diff
        pa, pb = Path(va["snapshot_path"]), Path(vb["snapshot_path"])
        if pa.exists() and pb.exists():
            suffix = pa.suffix.lower()
            if suffix == ".csv":
                result["content_diff"] = self._diff_csv(pa, pb)
            elif suffix == ".json":
                result["content_diff"] = self._diff_json(pa, pb)

        self._stats["total_diffs"] += 1
        self._log_op("diff", dataset=dataset_name, version_a=version_a, version_b=version_b)
        return result

    def _diff_csv(self, path_a: Path, path_b: Path) -> Dict[str, Any]:
        """CSV satır düzeyinde karşılaştırma."""
        hdrs_a, rows_a = _read_csv_rows(path_a)
        hdrs_b, rows_b = _read_csv_rows(path_b)

        def _key(r: Dict) -> str:
            return json.dumps(r, sort_keys=True, ensure_ascii=False)

        set_a = {_key(r) for r in rows_a}
        set_b = {_key(r) for r in rows_b}
        added, removed = set_b - set_a, set_a - set_b
        return {
            "type": "csv", "rows_in_a": len(rows_a), "rows_in_b": len(rows_b),
            "rows_added": len(added), "rows_removed": len(removed),
            "rows_unchanged": len(set_a & set_b),
            "headers_a": hdrs_a, "headers_b": hdrs_b,
            "added_samples": [json.loads(k) for k in list(added)[:20]],
            "removed_samples": [json.loads(k) for k in list(removed)[:20]],
        }

    def _diff_json(self, path_a: Path, path_b: Path) -> Dict[str, Any]:
        """JSON key düzeyinde karşılaştırma."""
        da, db = _read_json_data(path_a), _read_json_data(path_b)
        res: Dict[str, Any] = {"type": "json"}
        if isinstance(da, dict) and isinstance(db, dict):
            ka, kb = set(da.keys()), set(db.keys())
            res["keys_added"] = sorted(kb - ka)
            res["keys_removed"] = sorted(ka - kb)
            res["keys_unchanged"] = sorted(ka & kb)
            res["keys_changed"] = sorted(k for k in ka & kb if da[k] != db[k])
        elif isinstance(da, list) and isinstance(db, list):
            def _ser(items):
                s = set()
                for i in items:
                    try: s.add(json.dumps(i, sort_keys=True, ensure_ascii=False))
                    except (TypeError, ValueError): pass
                return s
            sa, sb = _ser(da), _ser(db)
            res.update({"items_in_a": len(da), "items_in_b": len(db),
                        "items_added": len(sb - sa), "items_removed": len(sa - sb),
                        "items_unchanged": len(sa & sb)})
        else:
            res["note"] = "Farklı veri tipleri, detaylı karşılaştırma yapılamadı"
        return res

    # ── Liste / sorgulama ──────────────────────────────────────────

    def list_datasets(self) -> List[Dict]:
        """Tüm veri setlerini listele."""
        result = []
        for name, ds in self._index.get("datasets", {}).items():
            versions = ds.get("versions", [])
            result.append({
                "name": name, "total_versions": len(versions),
                "latest_version": ds.get("latest_version"),
                "created_at": ds.get("created_at"),
                "latest_stats": versions[-1].get("stats", {}) if versions else {},
                "has_retention_policy": name in self._retention_policies,
            })
        return result

    def get_versions(self, dataset_name: str) -> List[Dict]:
        """Bir veri setinin tüm versiyonlarını listele."""
        ds = self._index["datasets"].get(dataset_name)
        if not ds:
            raise KeyError(f"Dataset bulunamadı: {dataset_name}")
        return ds.get("versions", [])

    def check_changes(self, file_path: str, dataset_name: Optional[str] = None) -> Dict:
        """Dosyanın son snapshot'tan bu yana değişip değişmediğini kontrol et."""
        source = Path(file_path)
        if not source.exists():
            return {"exists": False, "error": f"Dosya bulunamadı: {file_path}"}

        ds_name = dataset_name or source.stem
        cur_hash = _file_hash(source)
        cur_stats = _file_stats(source)

        ds = self._index["datasets"].get(ds_name)
        if not ds or not ds.get("versions"):
            return {"dataset": ds_name, "has_versions": False, "changed": True,
                    "current_hash": cur_hash[:12], "current_stats": cur_stats}

        latest = ds["versions"][-1]
        return {
            "dataset": ds_name, "has_versions": True, "changed": latest["hash"] != cur_hash,
            "current_hash": cur_hash[:12], "latest_version": latest["version"],
            "latest_hash": latest["hash"][:12],
            "current_stats": cur_stats, "latest_stats": latest.get("stats", {}),
        }

    # ── Dashboard ──────────────────────────────────────────────────

    def get_dashboard(self) -> Dict:
        """Dashboard özeti — istatistikler, son operasyonlar, dataset listesi."""
        self._refresh_stats()
        datasets = self._index.get("datasets", {})
        total_v = sum(len(d.get("versions", [])) for d in datasets.values())
        total_mb = sum(
            v.get("stats", {}).get("size_mb", 0)
            for d in datasets.values() for v in d.get("versions", [])
        )
        stb = self._stats["storage_bytes"]
        return {
            "total_datasets": len(datasets), "total_versions": total_v,
            "total_snapshot_size_mb": round(total_mb, 2),
            "tracker": {
                "total_snapshots_created": self._stats["total_snapshots"],
                "total_rollbacks": self._stats["total_rollbacks"],
                "total_diffs": self._stats["total_diffs"],
                "total_compressions": self._stats["total_compressions"],
                "total_verifications": self._stats["total_verifications"],
                "datasets_tracked": self._stats["datasets_tracked"],
                "storage_bytes": stb,
                "storage_mb": round(stb / (1024 * 1024), 2) if stb > 0 else 0,
            },
            "retention_policies": dict(self._retention_policies),
            "recent_operations": self._operation_log[-20:],
            "datasets": self.list_datasets(),
        }

    # ── Lineage (soy ağacı) ───────────────────────────────────────

    def get_lineage(self, dataset_name: str) -> Dict[str, Any]:
        """Dataset'in soy ağacını (parent→child ilişkileri) döndür."""
        ds = self._index["datasets"].get(dataset_name)
        if not ds:
            raise KeyError(f"Dataset bulunamadı: {dataset_name}")
        lineage = ds.get("lineage", [])
        tree: Dict[str, List[str]] = {}
        for e in lineage:
            p = e.get("parent") or "root"
            tree.setdefault(p, []).append(e.get("child", ""))
        return {
            "dataset": dataset_name, "total_versions": len(ds.get("versions", [])),
            "lineage_entries": lineage, "tree": tree,
            "root_versions": tree.get("root", []),
        }

    # ── Retention ─────────────────────────────────────────────────

    def set_retention(self, dataset_name: str, max_versions: int = 10) -> Dict[str, Any]:
        """Saklama politikası ayarla — max_versions aşıldığında eski versiyonlar silinir."""
        if max_versions < 1:
            raise ValueError("max_versions en az 1 olmalıdır")
        self._retention_policies[dataset_name] = max_versions
        self._log_op("set_retention", dataset=dataset_name, max_versions=max_versions)
        removed = self._apply_retention(dataset_name)
        return {
            "dataset": dataset_name, "max_versions": max_versions,
            "removed_count": len(removed),
            "removed_versions": [v["version"] for v in removed],
        }

    # ── Sıkıştırma ───────────────────────────────────────────────

    def compress_snapshot(self, dataset_name: str, version: str) -> Dict[str, Any]:
        """Snapshot'ı gzip ile sıkıştır (orijinal korunur, .gz eklenir)."""
        ds = self._index["datasets"].get(dataset_name)
        if not ds:
            raise KeyError(f"Dataset bulunamadı: {dataset_name}")
        target = self._find_version(ds, version)
        if not target:
            raise KeyError(f"Versiyon bulunamadı: {version}")

        snap = Path(target["snapshot_path"])
        if not snap.exists():
            raise FileNotFoundError(f"Snapshot dosyası bulunamadı: {snap}")

        gz_path = Path(str(snap) + ".gz")
        orig_size = snap.stat().st_size
        with open(snap, "rb") as fi, gzip.open(str(gz_path), "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo)

        comp_size = gz_path.stat().st_size
        ratio = round((1 - comp_size / orig_size) * 100, 1) if orig_size > 0 else 0

        target.update({"compressed": True, "compressed_path": str(gz_path),
                        "compressed_size_bytes": comp_size, "compression_ratio_pct": ratio})
        self._save_index()

        self._stats["total_compressions"] += 1
        self._log_op("compress_snapshot", dataset=dataset_name, version=version, ratio_pct=ratio)
        logger.info("snapshot_compressed", dataset=dataset_name, version=version, ratio=f"{ratio}%")
        return {
            "dataset": dataset_name, "version": version,
            "original_size_bytes": orig_size, "compressed_size_bytes": comp_size,
            "compression_ratio_pct": ratio, "compressed_path": str(gz_path),
        }

    # ── Bütünlük doğrulaması ─────────────────────────────────────

    def verify_integrity(self, dataset_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """SHA-256 bütünlük doğrulaması (version=None → tüm versiyonlar)."""
        ds = self._index["datasets"].get(dataset_name)
        if not ds:
            raise KeyError(f"Dataset bulunamadı: {dataset_name}")

        to_check = ds.get("versions", [])
        if version:
            to_check = [v for v in to_check if v["version"] == version]
            if not to_check:
                raise KeyError(f"Versiyon bulunamadı: {version}")

        results: List[Dict[str, Any]] = []
        all_valid = True
        for v in to_check:
            sp = Path(v["snapshot_path"])
            e: Dict[str, Any] = {"version": v["version"], "expected_hash": v["hash"][:12]}
            if not sp.exists():
                e.update({"status": "missing", "valid": False})
                all_valid = False
            else:
                ah = _file_hash(sp)
                valid = ah == v["hash"]
                e.update({"actual_hash": ah[:12], "valid": valid,
                          "status": "valid" if valid else "corrupted"})
                if not valid:
                    all_valid = False
            results.append(e)

        self._stats["total_verifications"] += 1
        self._log_op("verify_integrity", dataset=dataset_name, version=version or "all", all_valid=all_valid)
        return {"dataset": dataset_name, "all_valid": all_valid,
                "checked_count": len(results), "results": results}

    # ── Toplu (bulk) snapshot ────────────────────────────────────

    def create_bulk_snapshot(
        self, dataset_names: List[str], source_paths: List[str],
        description: str = "", created_by: str = "system",
    ) -> Dict[str, Any]:
        """Birden fazla dataset için tek seferde snapshot al."""
        if len(dataset_names) != len(source_paths):
            raise ValueError("dataset_names ve source_paths aynı uzunlukta olmalıdır")

        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for ds_name, src in zip(dataset_names, source_paths):
            try:
                r = self.create_snapshot(src, ds_name, description, created_by)
                results.append({"dataset": ds_name, "version": r.get("version"),
                                "status": "success", "skipped": r.get("skipped", False)})
            except Exception as e:
                errors.append({"dataset": ds_name, "source_path": src,
                               "status": "error", "error": str(e)})
                logger.warning("bulk_snapshot_error", dataset=ds_name, error=str(e))

        self._log_op("bulk_snapshot", total=len(dataset_names),
                      success=len(results), failed=len(errors))
        return {"total_requested": len(dataset_names), "successful": len(results),
                "failed": len(errors), "results": results, "errors": errors}

    # ── Depolama analitikleri ────────────────────────────────────

    def get_storage_stats(self) -> Dict[str, Any]:
        """Dataset bazında depolama kullanımı analizi."""
        datasets = self._index.get("datasets", {})
        per_ds: List[Dict[str, Any]] = []
        g_total = g_comp = 0

        for name, ds in datasets.items():
            versions = ds.get("versions", [])
            ds_bytes = ds_comp = comp_cnt = 0
            for v in versions:
                sz = v.get("stats", {}).get("size_bytes", 0)
                ds_bytes += sz
                if v.get("compressed"):
                    comp_cnt += 1
                    ds_comp += v.get("compressed_size_bytes", 0)
            avg = ds_bytes / len(versions) if versions else 0
            g_total += ds_bytes
            g_comp += ds_comp
            per_ds.append({
                "dataset": name, "version_count": len(versions),
                "total_bytes": ds_bytes, "total_mb": round(ds_bytes / (1024 * 1024), 2),
                "avg_snapshot_bytes": round(avg), "avg_snapshot_mb": round(avg / (1024 * 1024), 3),
                "compressed_versions": comp_cnt, "compressed_bytes": ds_comp,
                "retention_policy": self._retention_policies.get(name),
            })
        per_ds.sort(key=lambda x: x["total_bytes"], reverse=True)
        return {
            "grand_total_bytes": g_total, "grand_total_mb": round(g_total / (1024 * 1024), 2),
            "grand_compressed_bytes": g_comp, "grand_compressed_mb": round(g_comp / (1024 * 1024), 2),
            "total_datasets": len(datasets), "per_dataset": per_ds,
        }

    # ── Operasyon günlüğü ────────────────────────────────────────

    def get_operation_log(self, limit: int = 50, operation_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Operasyon günlüğünü döndür (en yeniden eskiye)."""
        log = self._operation_log
        if operation_filter:
            log = [e for e in log if e.get("operation") == operation_filter]
        return list(reversed(log[-limit:]))


# Singleton instance
data_version_manager = DataVersionManager()

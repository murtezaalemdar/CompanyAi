"""Model Registry — Model Versiyon Takibi ve Yaşam Döngüsü Yönetimi

Özellikleri:
- Model versiyonlama (staging / production / archived)
- Deployment geçmişi (kim, ne zaman, hangi duruma)
- Ollama model sağlık kontrolü
- Model karşılaştırma metrikleri
"""

import json
import time
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path
import structlog

logger = structlog.get_logger()

# ── Veri Depolama ────────────────────────────────────────────────
_REGISTRY_FILE = Path("data/model_registry.json")
_HISTORY_FILE = Path("data/model_deployment_history.json")


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Model Registry ──────────────────────────────────────────────

class ModelRegistry:
    """Model versiyon ve yaşam döngüsü yöneticisi."""

    STATUS_STAGING = "staging"
    STATUS_PRODUCTION = "production"
    STATUS_ARCHIVED = "archived"
    STATUS_TESTING = "testing"
    VALID_STATUSES = [STATUS_STAGING, STATUS_PRODUCTION, STATUS_ARCHIVED, STATUS_TESTING]

    def __init__(self):
        self._models = _load_json(_REGISTRY_FILE)
        if "models" not in self._models:
            self._models = {"models": {}, "created_at": _utcnow_str()}
        self._history = _load_json(_HISTORY_FILE)
        if "deployments" not in self._history:
            self._history = {"deployments": []}

    def _save(self):
        _save_json(_REGISTRY_FILE, self._models)
        _save_json(_HISTORY_FILE, self._history)

    def register_model(
        self,
        name: str,
        version: str,
        model_type: str = "llm",
        parameters: Optional[Dict] = None,
        description: str = "",
        registered_by: str = "system",
        size_gb: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Yeni model versiyonu kaydet."""
        model_id = f"{name}:{version}"
        entry = {
            "name": name,
            "version": version,
            "model_id": model_id,
            "model_type": model_type,  # llm, embedding, vision, custom
            "status": self.STATUS_STAGING,
            "parameters": parameters or {},
            "description": description,
            "size_gb": size_gb,
            "registered_by": registered_by,
            "registered_at": _utcnow_str(),
            "last_status_change": _utcnow_str(),
            "metrics": {},
            "tags": [],
        }
        self._models["models"][model_id] = entry
        self._save()
        logger.info("model_registered", model_id=model_id, by=registered_by)
        return entry

    def promote(
        self,
        model_id: str,
        target_status: str,
        promoted_by: str = "system",
        reason: str = "",
    ) -> Dict[str, Any]:
        """Model durumunu değiştir (staging → production, vb.)."""
        if target_status not in self.VALID_STATUSES:
            raise ValueError(f"Geçersiz status: {target_status}. Geçerli: {self.VALID_STATUSES}")

        model = self._models["models"].get(model_id)
        if not model:
            raise KeyError(f"Model bulunamadı: {model_id}")

        old_status = model["status"]

        # Production'a alınıyorsa, mevcut production modeli archive'a al
        if target_status == self.STATUS_PRODUCTION:
            for mid, m in self._models["models"].items():
                if m["model_type"] == model["model_type"] and m["status"] == self.STATUS_PRODUCTION and mid != model_id:
                    m["status"] = self.STATUS_ARCHIVED
                    m["last_status_change"] = _utcnow_str()
                    logger.info("model_auto_archived", model_id=mid)

        model["status"] = target_status
        model["last_status_change"] = _utcnow_str()

        # Deployment geçmişine kaydet
        deployment = {
            "model_id": model_id,
            "from_status": old_status,
            "to_status": target_status,
            "promoted_by": promoted_by,
            "reason": reason,
            "timestamp": _utcnow_str(),
        }
        self._history["deployments"].append(deployment)
        self._save()

        logger.info("model_promoted", model_id=model_id, from_s=old_status, to_s=target_status)
        return {**model, "deployment": deployment}

    def update_metrics(self, model_id: str, metrics: Dict[str, float]):
        """Model performans metriklerini güncelle."""
        model = self._models["models"].get(model_id)
        if not model:
            raise KeyError(f"Model bulunamadı: {model_id}")

        model["metrics"].update(metrics)
        model["metrics"]["last_updated"] = _utcnow_str()
        self._save()

    def get_production_model(self, model_type: str = "llm") -> Optional[Dict]:
        """Aktif production modelini döndür."""
        for m in self._models["models"].values():
            if m["model_type"] == model_type and m["status"] == self.STATUS_PRODUCTION:
                return m
        return None

    def list_models(self, model_type: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        """Modelleri listele (filtrelenebilir)."""
        result = []
        for m in self._models["models"].values():
            if model_type and m["model_type"] != model_type:
                continue
            if status and m["status"] != status:
                continue
            result.append(m)
        return sorted(result, key=lambda x: x.get("registered_at", ""), reverse=True)

    def get_deployment_history(self, model_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Deployment geçmişini döndür."""
        history = self._history.get("deployments", [])
        if model_id:
            history = [h for h in history if h["model_id"] == model_id]
        return history[-limit:]

    def delete_model(self, model_id: str, deleted_by: str = "system"):
        """Modeli registry'den sil (sadece archived olanlar silinebilir)."""
        model = self._models["models"].get(model_id)
        if not model:
            raise KeyError(f"Model bulunamadı: {model_id}")
        if model["status"] == self.STATUS_PRODUCTION:
            raise ValueError("Production'daki model silinemez. Önce archive edin.")

        del self._models["models"][model_id]
        self._save()
        logger.info("model_deleted", model_id=model_id, by=deleted_by)

    def compare_models(self, model_id_a: str, model_id_b: str) -> Dict:
        """İki modelin metriklerini karşılaştır."""
        a = self._models["models"].get(model_id_a)
        b = self._models["models"].get(model_id_b)
        if not a or not b:
            raise KeyError("Karşılaştırılacak modellerden biri bulunamadı")

        metrics_a = a.get("metrics", {})
        metrics_b = b.get("metrics", {})
        all_keys = set(list(metrics_a.keys()) + list(metrics_b.keys())) - {"last_updated"}

        comparison = {}
        for key in sorted(all_keys):
            va = metrics_a.get(key)
            vb = metrics_b.get(key)
            winner = None
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                winner = model_id_a if va > vb else model_id_b if vb > va else "eşit"
            comparison[key] = {"model_a": va, "model_b": vb, "winner": winner}

        return {
            "model_a": {"id": model_id_a, "status": a["status"]},
            "model_b": {"id": model_id_b, "status": b["status"]},
            "metrics_comparison": comparison,
        }

    async def sync_with_ollama(self) -> Dict:
        """Ollama'daki modelleri otomatik kaydet."""
        try:
            from app.llm.client import ollama_client
            models = await ollama_client.get_models()
            synced = []
            for model_name in models:
                model_id = f"{model_name}:latest"
                if model_id not in self._models["models"]:
                    self.register_model(
                        name=model_name,
                        version="latest",
                        model_type="llm",
                        description=f"Ollama'dan otomatik senkronize: {model_name}",
                        registered_by="ollama_sync",
                    )
                    synced.append(model_name)

            # Aktif modeli production'a al
            from app.config import Settings
            settings = Settings()
            active_id = f"{settings.LLM_MODEL}:latest"
            if active_id in self._models["models"]:
                if self._models["models"][active_id]["status"] != self.STATUS_PRODUCTION:
                    self.promote(active_id, self.STATUS_PRODUCTION, "ollama_sync", "Aktif config modeli")

            return {"synced": synced, "total_models": len(models)}
        except Exception as e:
            logger.error("ollama_sync_failed", error=str(e))
            return {"error": str(e)}

    def get_dashboard(self) -> Dict:
        """Registry özet dashboard."""
        models = self._models.get("models", {})
        status_counts = {}
        type_counts = {}
        for m in models.values():
            status_counts[m["status"]] = status_counts.get(m["status"], 0) + 1
            type_counts[m["model_type"]] = type_counts.get(m["model_type"], 0) + 1

        return {
            "total_models": len(models),
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "production_model": self.get_production_model(),
            "recent_deployments": self.get_deployment_history(limit=5),
        }


# Singleton instance
model_registry = ModelRegistry()

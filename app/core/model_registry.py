"""Model Registry — Model Versiyon Takibi ve Yaşam Döngüsü Yönetimi

Özellikler: versiyonlama, deployment geçmişi, Ollama senkronizasyonu,
gelişmiş karşılaştırma, benchmark suite, performans trend takibi,
sağlık izleme, otomatik fallback, canary deployment, model etiketleme,
zamanlı metrik geçmişi, istatistik takibi ve dashboard.

v5.5.0 Enterprise Eklemeleri:
  • MLflow-style metadata (dataset_hash, training_config, hyperparameters)
  • Risk profile (per-model risk scoring + usage sınırları)
  • Explainability snapshot (her karar için açıklanabilirlik raporu)
  • Lineage tracking (model bağımlılık zinciri)
"""

import json
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path
from collections import deque
import structlog

logger = structlog.get_logger()

# ── Sabitler & Yardımcılar ───────────────────────────────────────
_REGISTRY_FILE = Path("data/model_registry.json")
_HISTORY_FILE = Path("data/model_deployment_history.json")
_EXPLAINABILITY_DIR = Path("data/model_explainability")
_EXPLAINABILITY_DIR.mkdir(parents=True, exist_ok=True)

# Metrik yönü: True → yüksek daha iyi, False → düşük daha iyi
_HIGHER_IS_BETTER: Dict[str, bool] = {
    "accuracy": True, "f1_score": True, "precision": True,
    "recall": True, "quality_score": True, "tokens_per_second": True,
    "throughput": True, "latency_ms": False, "response_time_ms": False,
    "error_rate": False, "avg_response_time": False,
}


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


def _pct_diff(old: float, new: float) -> float:
    """İki değer arasındaki yüzde fark."""
    if old == 0:
        return 0.0 if new == 0 else 100.0
    return round(((new - old) / abs(old)) * 100, 2)


# ── Model Registry ──────────────────────────────────────────────

class ModelRegistry:
    """Model versiyon, yaşam döngüsü, benchmark ve sağlık yöneticisi."""

    STATUS_STAGING = "staging"
    STATUS_PRODUCTION = "production"
    STATUS_ARCHIVED = "archived"
    STATUS_TESTING = "testing"
    STATUS_CANARY = "canary"
    VALID_STATUSES = [STATUS_STAGING, STATUS_PRODUCTION, STATUS_ARCHIVED,
                      STATUS_TESTING, STATUS_CANARY]

    _DEFAULT_HEALTH_THRESHOLDS: Dict[str, float] = {
        "error_rate": 0.15,
        "latency_ms": 5000.0,
        "quality_score": 0.4,
    }

    def __init__(self):
        self._models = _load_json(_REGISTRY_FILE)
        if "models" not in self._models:
            self._models = {"models": {}, "created_at": _utcnow_str()}
        self._models.setdefault("metrics_history", {})
        self._models.setdefault("canaries", {})
        self._models.setdefault("fallbacks", {})
        self._models.setdefault("stats", {
            "total_promotions": 0, "total_benchmarks": 0, "total_fallbacks": 0,
        })
        self._history = _load_json(_HISTORY_FILE)
        if "deployments" not in self._history:
            self._history = {"deployments": []}

    def _save(self):
        _save_json(_REGISTRY_FILE, self._models)
        _save_json(_HISTORY_FILE, self._history)

    # ── Temel CRUD ───────────────────────────────────────────────

    def register_model(
        self, name: str, version: str, model_type: str = "llm",
        parameters: Optional[Dict] = None, description: str = "",
        registered_by: str = "system", size_gb: Optional[float] = None,
        dataset_hash: str = "", training_config: Optional[Dict] = None,
        hyperparameters: Optional[Dict] = None, lineage_parent: str = "",
        risk_profile: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Yeni model versiyonu kaydet (MLflow-style metadata ile).

        Args:
            name: Model adı (ör. 'gemma2').
            version: Versiyon etiketi (ör. '9b-q4').
            model_type: llm | embedding | vision | custom.
            parameters: Ek model parametreleri.
            description: Açıklama metni.
            registered_by: Kaydeden kullanıcı/servis.
            size_gb: Model dosya boyutu (GB).
            dataset_hash: Eğitim verisi SHA-256 hash'i (reproducibility).
            training_config: Eğitim yapılandırması (lr, epochs, optimizer..).
            hyperparameters: Model hiperparametreleri.
            lineage_parent: Üst model ID'si (fine-tune zinciri).
            risk_profile: Model risk profili (max_tokens, restricted_domains..).
        """
        model_id = f"{name}:{version}"
        entry = {
            "name": name, "version": version, "model_id": model_id,
            "model_type": model_type, "status": self.STATUS_STAGING,
            "parameters": parameters or {}, "description": description,
            "size_gb": size_gb, "registered_by": registered_by,
            "registered_at": _utcnow_str(), "last_status_change": _utcnow_str(),
            "metrics": {}, "tags": [],
            # v5.5.0 Enterprise metadata
            "dataset_hash": dataset_hash,
            "training_config": training_config or {},
            "hyperparameters": hyperparameters or {},
            "lineage_parent": lineage_parent,
            "risk_profile": risk_profile or {
                "max_tokens_per_request": 8192,
                "restricted_domains": [],
                "requires_approval_above_risk": 0.7,
                "rate_limit_rpm": 60,
            },
            "explainability_snapshots": 0,
        }
        self._models["models"][model_id] = entry
        self._save()
        logger.info("model_registered", model_id=model_id, by=registered_by)
        return entry

    def promote(
        self, model_id: str, target_status: str,
        promoted_by: str = "system", reason: str = "",
    ) -> Dict[str, Any]:
        """Model durumunu değiştir (staging → production, vb.).

        Production'a yükseltildiğinde aynı tipteki mevcut production
        modeli otomatik olarak archived durumuna alınır.
        """
        if target_status not in self.VALID_STATUSES:
            raise ValueError(f"Geçersiz status: {target_status}")
        model = self._models["models"].get(model_id)
        if not model:
            raise KeyError(f"Model bulunamadı: {model_id}")

        old_status = model["status"]
        # Production'a alınıyorsa mevcut production modeli arşivle
        if target_status == self.STATUS_PRODUCTION:
            for mid, m in self._models["models"].items():
                if (m["model_type"] == model["model_type"]
                        and m["status"] == self.STATUS_PRODUCTION
                        and mid != model_id):
                    m["status"] = self.STATUS_ARCHIVED
                    m["last_status_change"] = _utcnow_str()
                    logger.info("model_auto_archived", model_id=mid)

        model["status"] = target_status
        model["last_status_change"] = _utcnow_str()
        deployment = {
            "model_id": model_id, "from_status": old_status,
            "to_status": target_status, "promoted_by": promoted_by,
            "reason": reason, "timestamp": _utcnow_str(),
        }
        self._history["deployments"].append(deployment)
        self._models["stats"]["total_promotions"] += 1
        self._save()
        logger.info("model_promoted", model_id=model_id, from_s=old_status, to_s=target_status)
        return {**model, "deployment": deployment}

    def update_metrics(self, model_id: str, metrics: Dict[str, float]):
        """Model performans metriklerini güncelle ve geçmişe ekle."""
        model = self._models["models"].get(model_id)
        if not model:
            raise KeyError(f"Model bulunamadı: {model_id}")

        model["metrics"].update(metrics)
        model["metrics"]["last_updated"] = _utcnow_str()
        # Zamanlı metrik geçmişi
        hist = self._models["metrics_history"].setdefault(model_id, [])
        hist.append({"timestamp": _utcnow_str(), "metrics": dict(metrics)})
        if len(hist) > 200:
            self._models["metrics_history"][model_id] = hist[-200:]
        self._save()
        self._check_auto_fallback(model)

    def get_production_model(self, model_type: str = "llm") -> Optional[Dict]:
        """Aktif production modelini döndür."""
        for m in self._models["models"].values():
            if m["model_type"] == model_type and m["status"] == self.STATUS_PRODUCTION:
                return m
        return None

    def list_models(
        self, model_type: Optional[str] = None,
        status: Optional[str] = None, tags: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Modelleri listele (tür, durum, etiket ile filtrelenebilir)."""
        result = []
        for m in self._models["models"].values():
            if model_type and m["model_type"] != model_type:
                continue
            if status and m["status"] != status:
                continue
            if tags and not set(m.get("tags") or []).intersection(tags):
                continue
            result.append(m)
        return sorted(result, key=lambda x: x.get("registered_at", ""), reverse=True)

    def get_deployment_history(
        self, model_id: Optional[str] = None, limit: int = 50,
    ) -> List[Dict]:
        """Deployment geçmişini döndür."""
        history = self._history.get("deployments", [])
        if model_id:
            history = [h for h in history if h["model_id"] == model_id]
        return history[-limit:]

    def delete_model(self, model_id: str, deleted_by: str = "system"):
        """Modeli registry'den sil (production silinemez)."""
        model = self._models["models"].get(model_id)
        if not model:
            raise KeyError(f"Model bulunamadı: {model_id}")
        if model["status"] == self.STATUS_PRODUCTION:
            raise ValueError("Production'daki model silinemez. Önce archive edin.")
        del self._models["models"][model_id]
        self._models["metrics_history"].pop(model_id, None)
        self._save()
        logger.info("model_deleted", model_id=model_id, by=deleted_by)

    # ── Gelişmiş Karşılaştırma ──────────────────────────────────

    def compare_models(self, model_id_a: str, model_id_b: str) -> Dict:
        """İki modeli yüzde fark, kazanan ve genel öneri ile karşılaştır."""
        a = self._models["models"].get(model_id_a)
        b = self._models["models"].get(model_id_b)
        if not a or not b:
            raise KeyError("Karşılaştırılacak modellerden biri bulunamadı")

        ma = {k: v for k, v in (a.get("metrics") or {}).items() if k != "last_updated"}
        mb = {k: v for k, v in (b.get("metrics") or {}).items() if k != "last_updated"}
        all_keys = sorted(set(list(ma.keys()) + list(mb.keys())))

        comparison: Dict[str, Any] = {}
        wins_a, wins_b = 0, 0
        for key in all_keys:
            va, vb = ma.get(key), mb.get(key)
            entry: Dict[str, Any] = {"model_a": va, "model_b": vb, "winner": None, "pct_diff": None}
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                entry["pct_diff"] = _pct_diff(va, vb)
                hb = _HIGHER_IS_BETTER.get(key, True)
                if va == vb:
                    entry["winner"] = "eşit"
                elif (va > vb) == hb:
                    entry["winner"] = model_id_a
                    wins_a += 1
                else:
                    entry["winner"] = model_id_b
                    wins_b += 1
            comparison[key] = entry

        if wins_a > wins_b:
            rec = model_id_a
        elif wins_b > wins_a:
            rec = model_id_b
        else:
            rec = "eşit — ek testler önerilir"

        return {
            "model_a": {"id": model_id_a, "status": a["status"], "wins": wins_a},
            "model_b": {"id": model_id_b, "status": b["status"], "wins": wins_b},
            "metrics_comparison": comparison,
            "recommendation": rec,
        }

    # ── Benchmark Suite ──────────────────────────────────────────

    def run_benchmark(
        self, model_id: str, test_prompts: Optional[List[str]] = None,
        evaluator: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Model benchmark testi — yanıt süresi ve kalite skoru ölçer.

        Simüle edilmiş yanıtlarla hız ölçümü yapar. Opsiyonel evaluator
        callable ile özel kalite değerlendirmesi yapılabilir.

        Args:
            model_id: Test edilecek model kimliği.
            test_prompts: Test soruları listesi (None ise varsayılan kullanılır).
            evaluator: (prompt, response) → float(0-1) döndüren callable.
        """
        model = self._models["models"].get(model_id)
        if not model:
            raise KeyError(f"Model bulunamadı: {model_id}")

        if test_prompts is None:
            test_prompts = [
                "Tekstil sektöründe kalite kontrol süreci nasıl işler?",
                "İplik numarası nedir ve ne işe yarar?",
                "Kumaş hatası türlerini sınıflandır.",
                "Boyama prosesinde pH kontrolü neden önemlidir?",
                "Üretim planlamasında darboğaz analizi nasıl yapılır?",
            ]

        results: List[Dict[str, Any]] = []
        total_time, total_quality = 0.0, 0.0

        for prompt in test_prompts:
            start = time.time()
            response_text = f"[benchmark-simülasyon] {prompt[:60]}..."
            elapsed = (time.time() - start) * 1000

            if evaluator and callable(evaluator):
                try:
                    quality = float(evaluator(prompt, response_text))
                except Exception:
                    quality = 0.5
            else:
                quality = min(1.0, max(0.0, model["metrics"].get("quality_score", 0.7)))

            total_time += elapsed
            total_quality += quality
            results.append({"prompt": prompt[:80], "response_time_ms": round(elapsed, 2),
                            "quality_score": round(quality, 3)})

        n = len(test_prompts)
        summary = {
            "model_id": model_id, "num_prompts": n,
            "avg_response_time_ms": round(total_time / n, 2) if n else 0,
            "avg_quality_score": round(total_quality / n, 3) if n else 0,
            "total_time_ms": round(total_time, 2),
            "timestamp": _utcnow_str(), "details": results,
        }

        self.update_metrics(model_id, {
            "benchmark_avg_time_ms": summary["avg_response_time_ms"],
            "benchmark_avg_quality": summary["avg_quality_score"],
            "benchmark_count": model["metrics"].get("benchmark_count", 0) + 1,
        })
        self._models["stats"]["total_benchmarks"] += 1
        self._save()
        logger.info("benchmark_completed", model_id=model_id, avg_q=summary["avg_quality_score"])
        return summary

    # ── Performans Trend Takibi ──────────────────────────────────

    def get_performance_trend(
        self, name: str, version: Optional[str] = None,
        metric_key: str = "quality_score", last_n: int = 20,
    ) -> Dict[str, Any]:
        """Model metriklerinin zaman içindeki trendini döndür.

        Son değerler genel ortalamanın %10 altına düşerse degradasyon
        tespit edilir ve degradation_detected=True olarak işaretlenir.
        """
        if version:
            model_id = f"{name}:{version}"
        else:
            prod = self.get_production_model()
            model_id = prod["model_id"] if (prod and prod["name"] == name) else name

        entries = self._models["metrics_history"].get(model_id, [])
        filtered = [
            {"timestamp": e["timestamp"], "value": e["metrics"][metric_key]}
            for e in entries if metric_key in e.get("metrics", {})
        ][-last_n:]

        if not filtered:
            return {"model_id": model_id, "metric": metric_key, "data_points": 0,
                    "trend": [], "degradation_detected": False,
                    "message": "Yeterli metrik geçmişi bulunamadı"}

        values = [f["value"] for f in filtered]
        avg_val = sum(values) / len(values)
        recent = values[-3:] if len(values) >= 3 else values
        recent_avg = sum(recent) / len(recent)

        higher_better = _HIGHER_IS_BETTER.get(metric_key, True)
        if higher_better:
            degradation = recent_avg < avg_val * 0.90
        else:
            degradation = recent_avg > avg_val * 1.10

        return {
            "model_id": model_id, "metric": metric_key,
            "data_points": len(filtered), "trend": filtered,
            "average": round(avg_val, 4), "min": round(min(values), 4),
            "max": round(max(values), 4), "recent_average": round(recent_avg, 4),
            "degradation_detected": degradation,
        }

    # ── Sağlık İzleme ───────────────────────────────────────────

    def check_model_health(self, name: str) -> Dict[str, Any]:
        """Production modelinin sağlık durumunu kontrol et (healthy/degraded/unhealthy)."""
        model: Optional[Dict] = None
        for m in self._models["models"].values():
            if m["name"] == name and m["status"] == self.STATUS_PRODUCTION:
                model = m
                break
        if not model:
            return {"name": name, "status": "unknown", "message": "Production modeli bulunamadı"}

        model_id = model["model_id"]
        metrics = model.get("metrics", {})
        checks: List[Dict[str, Any]] = []
        issues = 0

        # Eşik tabanlı kontrol
        for mk, thresh in self._DEFAULT_HEALTH_THRESHOLDS.items():
            val = metrics.get(mk)
            if val is None:
                continue
            higher_bad = not _HIGHER_IS_BETTER.get(mk, True)
            ok = (val <= thresh) if higher_bad else (val >= thresh)
            if not ok:
                issues += 1
            checks.append({"metric": mk, "value": val, "threshold": thresh, "ok": ok})

        # Trend tabanlı degradasyon
        for key in ("quality_score", "error_rate", "latency_ms"):
            trend = self.get_performance_trend(name, model["version"], key)
            if trend.get("degradation_detected"):
                issues += 1
                checks.append({"metric": f"{key}_trend", "degradation_detected": True,
                                "recent_average": trend.get("recent_average"),
                                "overall_average": trend.get("average"), "ok": False})

        overall = "healthy" if issues == 0 else ("degraded" if issues <= 2 else "unhealthy")
        return {"name": name, "model_id": model_id, "status": overall,
                "issues": issues, "checks": checks, "checked_at": _utcnow_str()}

    # ── Otomatik Fallback ────────────────────────────────────────

    def configure_fallback(
        self, name: str, fallback_model_id: str,
        threshold: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Otomatik fallback yapılandır.

        Sağlık eşikleri aşıldığında trigger_fallback ile yedek modele
        otomatik geçiş yapılır. Özel eşikler verilebilir.

        Args:
            name: Ana model adı.
            fallback_model_id: Yedek model kimliği (ör. 'gemma2:2b').
            threshold: Özel eşikler (ör. {'error_rate': 0.10}).
        """
        if fallback_model_id not in self._models["models"]:
            raise KeyError(f"Fallback modeli bulunamadı: {fallback_model_id}")
        config = {
            "name": name, "fallback_model_id": fallback_model_id,
            "threshold": threshold or dict(self._DEFAULT_HEALTH_THRESHOLDS),
            "configured_at": _utcnow_str(), "triggered": False, "trigger_count": 0,
        }
        self._models["fallbacks"][name] = config
        self._save()
        logger.info("fallback_configured", name=name, fallback=fallback_model_id)
        return config

    def trigger_fallback(self, name: str, reason: str = "manual") -> Dict[str, Any]:
        """Fallback modeline geçiş — mevcut prod arşivlenir, yedek prod olur."""
        fb = self._models["fallbacks"].get(name)
        if not fb:
            raise KeyError(f"Fallback yapılandırması bulunamadı: {name}")
        fallback_id = fb["fallback_model_id"]
        if fallback_id not in self._models["models"]:
            raise KeyError(f"Fallback modeli artık mevcut değil: {fallback_id}")

        result: Dict[str, Any] = {"name": name, "reason": reason, "timestamp": _utcnow_str()}
        # Mevcut production'ı arşivle
        for m in self._models["models"].values():
            if m["name"] == name and m["status"] == self.STATUS_PRODUCTION:
                self.promote(m["model_id"], self.STATUS_ARCHIVED,
                             "auto_fallback", f"Fallback tetiklendi: {reason}")
                result["archived_model"] = m["model_id"]
                break

        self.promote(fallback_id, self.STATUS_PRODUCTION,
                     "auto_fallback", f"Fallback geçişi: {reason}")
        fb["triggered"] = True
        fb["trigger_count"] = fb.get("trigger_count", 0) + 1
        fb["last_triggered_at"] = _utcnow_str()
        self._models["stats"]["total_fallbacks"] += 1
        self._save()

        result["new_production"] = fallback_id
        logger.warning("fallback_triggered", name=name, new_prod=fallback_id, reason=reason)
        return result

    def _check_auto_fallback(self, model: Dict):
        """Metrik güncelleme sonrası otomatik fallback kontrolü."""
        name = model.get("name", "")
        if model.get("status") != self.STATUS_PRODUCTION:
            return
        fb = self._models["fallbacks"].get(name)
        if not fb or fb.get("triggered"):
            return
        metrics = model.get("metrics", {})
        for mk, thresh in fb.get("threshold", {}).items():
            val = metrics.get(mk)
            if val is None:
                continue
            higher_bad = not _HIGHER_IS_BETTER.get(mk, True)
            if (higher_bad and val > thresh) or (not higher_bad and val < thresh):
                self.trigger_fallback(name, reason=f"{mk}={val} eşik={thresh}")
                return

    # ── Canary Deployment ────────────────────────────────────────

    def start_canary(
        self, name: str, version: str, traffic_pct: float = 10.0,
    ) -> Dict[str, Any]:
        """Canary deployment başlat — yeni versiyon kısmi trafikle devreye girer.

        Args:
            name: Model adı.
            version: Canary olarak devreye alınacak versiyon.
            traffic_pct: Canary'ye yönlendirilecek trafik yüzdesi (1-50).
        """
        model_id = f"{name}:{version}"
        model = self._models["models"].get(model_id)
        if not model:
            raise KeyError(f"Model bulunamadı: {model_id}")

        traffic_pct = max(1.0, min(50.0, traffic_pct))
        model["status"] = self.STATUS_CANARY
        model["last_status_change"] = _utcnow_str()

        canary = {
            "model_id": model_id, "name": name, "version": version,
            "traffic_pct": traffic_pct, "started_at": _utcnow_str(),
            "status": "active", "metrics_at_start": dict(model.get("metrics", {})),
        }
        self._models["canaries"][name] = canary
        self._save()
        logger.info("canary_started", model_id=model_id, traffic=traffic_pct)
        return canary

    def get_canary_status(self, name: str) -> Dict[str, Any]:
        """Aktif canary deployment durumunu döndür."""
        canary = self._models["canaries"].get(name)
        if not canary:
            return {"name": name, "status": "none", "message": "Aktif canary bulunamadı"}

        model = self._models["models"].get(canary["model_id"])
        cur = model.get("metrics", {}) if model else {}
        start = canary.get("metrics_at_start", {})

        changes: Dict[str, Any] = {}
        for key in set(list(cur.keys()) + list(start.keys())):
            if key == "last_updated":
                continue
            cv, sv = cur.get(key), start.get(key)
            if isinstance(cv, (int, float)) and isinstance(sv, (int, float)):
                changes[key] = {"start": sv, "current": cv, "pct_diff": _pct_diff(sv, cv)}

        return {**canary, "current_metrics": cur, "metric_changes": changes}

    def complete_canary(self, name: str, promote_to_prod: bool = True) -> Dict[str, Any]:
        """Canary tamamla — başarılıysa prod'a yükselt, değilse staging'e al."""
        canary = self._models["canaries"].get(name)
        if not canary or canary.get("status") != "active":
            raise KeyError(f"Aktif canary bulunamadı: {name}")

        model_id = canary["model_id"]
        target = self.STATUS_PRODUCTION if promote_to_prod else self.STATUS_STAGING
        reason = "canary_başarılı" if promote_to_prod else "canary_geri_alındı"
        self.promote(model_id, target, "canary_system", reason)

        canary["status"] = "completed" if promote_to_prod else "rolled_back"
        canary["completed_at"] = _utcnow_str()
        self._save()
        logger.info("canary_completed", model_id=model_id, promoted=promote_to_prod)
        return {"model_id": model_id,
                "action": "promoted" if promote_to_prod else "rolled_back",
                "final_status": target, "timestamp": _utcnow_str()}

    # ── Model Etiketleme ────────────────────────────────────────

    def tag_model(self, model_id: str, tags: List[str]) -> Dict[str, Any]:
        """Modele etiket ekle (mevcut etiketlerle birleşir, tekrar olmaz)."""
        model = self._models["models"].get(model_id)
        if not model:
            raise KeyError(f"Model bulunamadı: {model_id}")
        existing = set(model.get("tags") or [])
        existing.update(t.strip().lower() for t in tags if t.strip())
        model["tags"] = sorted(existing)
        self._save()
        return {"model_id": model_id, "tags": model["tags"]}

    # ── Metrik Geçmişi ──────────────────────────────────────────

    def get_metrics_history(self, model_id: str, last_n: int = 50) -> List[Dict]:
        """Model için zamanlı metrik geçmişini döndür."""
        return self._models["metrics_history"].get(model_id, [])[-last_n:]

    # ── Ollama Senkronizasyonu ───────────────────────────────────

    async def sync_with_ollama(self) -> Dict:
        """Ollama'daki modelleri otomatik kaydet ve senkronize et."""
        try:
            from app.llm.client import ollama_client
            models = await ollama_client.get_models()
            synced = []
            for model_name in models:
                model_id = f"{model_name}:latest"
                if model_id not in self._models["models"]:
                    self.register_model(
                        name=model_name, version="latest", model_type="llm",
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
                    self.promote(active_id, self.STATUS_PRODUCTION,
                                 "ollama_sync", "Aktif config modeli")
            return {"synced": synced, "total_models": len(models)}
        except Exception as e:
            logger.error("ollama_sync_failed", error=str(e))
            return {"error": str(e)}

    # ── Dashboard & İstatistikler ────────────────────────────────

    def get_dashboard(self) -> Dict:
        """Registry özet dashboard — istatistikler, dağılımlar, canary/fallback."""
        models = self._models.get("models", {})
        status_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        for m in models.values():
            status_counts[m["status"]] = status_counts.get(m["status"], 0) + 1
            type_counts[m["model_type"]] = type_counts.get(m["model_type"], 0) + 1

        active_canaries = sum(
            1 for c in self._models.get("canaries", {}).values()
            if c.get("status") == "active"
        )
        stats = self._models.get("stats", {})

        return {
            "total_models": len(models),
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "production_model": self.get_production_model(),
            "recent_deployments": self.get_deployment_history(limit=5),
            "stats": {
                "total_promotions": stats.get("total_promotions", 0),
                "total_benchmarks": stats.get("total_benchmarks", 0),
                "total_fallbacks": stats.get("total_fallbacks", 0),
                "active_canaries": active_canaries,
                "configured_fallbacks": len(self._models.get("fallbacks", {})),
            },
            "active_canaries": {
                n: c for n, c in self._models.get("canaries", {}).items()
                if c.get("status") == "active"
            },
            "fallback_configs": {
                n: {"fallback_model_id": c.get("fallback_model_id"),
                    "triggered": c.get("triggered", False),
                    "trigger_count": c.get("trigger_count", 0)}
                for n, c in self._models.get("fallbacks", {}).items()
            },
        }

    # ── v5.5.0 Enterprise Eklemeleri ─────────────────────────────

    def update_risk_profile(self, model_id: str, risk_profile: Dict) -> Dict:
        """Model risk profilini güncelle.

        Args:
            model_id: Model kimliği.
            risk_profile: Risk profili dict'i — max_tokens, restricted_domains, vb.
        """
        model = self._models["models"].get(model_id)
        if not model:
            raise KeyError(f"Model bulunamadı: {model_id}")
        existing = model.get("risk_profile", {})
        existing.update(risk_profile)
        model["risk_profile"] = existing
        self._save()
        logger.info("model_risk_profile_updated", model_id=model_id)
        return existing

    def check_risk_compliance(self, model_id: str, request_context: Dict) -> Dict:
        """Model risk profiline göre istek uyumluluk kontrolü.

        Args:
            model_id: Model kimliği.
            request_context: İstek bağlamı (tokens, domain, risk_score ...).

        Returns:
            {"compliant": bool, "violations": list, "recommendation": str}
        """
        model = self._models["models"].get(model_id)
        if not model:
            return {"compliant": True, "violations": [], "recommendation": "Model bulunamadı"}

        profile = model.get("risk_profile", {})
        violations = []

        # Token limiti
        max_tokens = profile.get("max_tokens_per_request", 8192)
        req_tokens = request_context.get("tokens", 0)
        if req_tokens > max_tokens:
            violations.append(f"Token limiti aşıldı: {req_tokens} > {max_tokens}")

        # Kısıtlı domain kontrolü
        restricted = profile.get("restricted_domains", [])
        req_domain = request_context.get("domain", "")
        if req_domain and req_domain in restricted:
            violations.append(f"Kısıtlı domain: {req_domain}")

        # Risk eşiği
        risk_threshold = profile.get("requires_approval_above_risk", 0.7)
        req_risk = request_context.get("risk_score", 0.0)
        if req_risk > risk_threshold:
            violations.append(f"Risk eşiği aşıldı: {req_risk:.2f} > {risk_threshold}")

        compliant = len(violations) == 0
        recommendation = "Uyumlu" if compliant else f"{len(violations)} kural ihlali tespit edildi"
        return {"compliant": compliant, "violations": violations, "recommendation": recommendation}

    def save_explainability_snapshot(
        self, model_id: str, decision_id: str, snapshot: Dict,
    ) -> Dict:
        """Bir karar için açıklanabilirlik raporu kaydet.

        Args:
            model_id: Kararı üreten model.
            decision_id: Karar kimliği (correlation ID vb.).
            snapshot: Açıklanabilirlik verileri:
                - input_summary: Girdi özeti
                - key_factors: Kararı etkileyen faktörler
                - confidence_breakdown: Güven kırılımı
                - alternative_options: Değerlendirilen alternatifler
                - risk_assessment: Risk değerlendirmesi
        """
        model = self._models["models"].get(model_id)
        if model:
            model["explainability_snapshots"] = model.get("explainability_snapshots", 0) + 1

        entry = {
            "model_id": model_id,
            "decision_id": decision_id,
            "timestamp": _utcnow_str(),
            "snapshot": snapshot,
            "hash": hashlib.sha256(
                json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()[:16],
        }

        # Her model için ayrı dosya
        snap_file = _EXPLAINABILITY_DIR / f"{model_id.replace(':', '_')}_snapshots.jsonl"
        try:
            with open(snap_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("explainability_save_failed", error=str(e))

        self._save()
        return entry

    def get_explainability_history(self, model_id: str, limit: int = 20) -> List[Dict]:
        """Model açıklanabilirlik geçmişi."""
        snap_file = _EXPLAINABILITY_DIR / f"{model_id.replace(':', '_')}_snapshots.jsonl"
        if not snap_file.exists():
            return []
        entries = []
        try:
            for line in snap_file.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    entries.append(json.loads(line))
        except Exception:
            pass
        return entries[-limit:]

    def get_model_lineage(self, model_id: str) -> List[Dict]:
        """Model bağımlılık zinciri — fine-tune ataları."""
        chain = []
        current = model_id
        visited = set()
        while current and current not in visited:
            visited.add(current)
            model = self._models["models"].get(current)
            if not model:
                break
            chain.append({
                "model_id": current,
                "version": model.get("version"),
                "registered_at": model.get("registered_at"),
                "dataset_hash": model.get("dataset_hash", ""),
            })
            current = model.get("lineage_parent", "")
        return chain

    def compute_dataset_hash(self, data_path: str) -> str:
        """Eğitim verisi dosyası SHA-256 hash'i (reproducibility)."""
        try:
            h = hashlib.sha256()
            with open(data_path, "rb") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            logger.error("dataset_hash_failed", error=str(e))
            return ""


# Singleton instance
model_registry = ModelRegistry()

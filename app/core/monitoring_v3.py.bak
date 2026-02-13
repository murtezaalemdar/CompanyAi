"""Gelişmiş Monitoring & Telemetry — Sistem İzleme ve Uyarı

Mevcut CPU/RAM/Disk izlemeyi güçlendirir:
- GPU kullanımı (Ollama üzerinden veya nvidia-smi)
- Hata oranı takibi (error rate)
- API yanıt süresi istatistikleri (percentile)
- Uyarı sistemi (threshold-based alerts)
- Sağlık puanı (health score)
"""

import json
import time
import subprocess
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import deque
from pathlib import Path
import structlog

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = structlog.get_logger()

_ALERTS_FILE = Path("data/monitoring_alerts.json")
_METRICS_FILE = Path("data/monitoring_metrics.json")


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── GPU İzleme ──────────────────────────────────────────────────

def get_gpu_info() -> Dict:
    """GPU bilgilerini al (nvidia-smi veya Ollama üzerinden)."""
    gpu_info = {"available": False, "gpus": []}

    # 1. nvidia-smi dene
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for i, line in enumerate(result.stdout.strip().split("\n")):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    gpu_info["gpus"].append({
                        "index": i,
                        "name": parts[0],
                        "memory_total_mb": int(parts[1]),
                        "memory_used_mb": int(parts[2]),
                        "memory_free_mb": int(parts[3]),
                        "utilization_percent": int(parts[4]),
                        "temperature_c": int(parts[5]),
                        "memory_utilization_percent": round(int(parts[2]) / int(parts[1]) * 100, 1) if int(parts[1]) > 0 else 0,
                    })
            gpu_info["available"] = True
            return gpu_info
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # 2. Ollama ps (model yüklü mü kontrol)
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/ps"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            models = data.get("models", [])
            for m in models:
                gpu_info["gpus"].append({
                    "name": "Ollama Model",
                    "model": m.get("name", "unknown"),
                    "size_gb": round(m.get("size", 0) / (1024**3), 1),
                    "vram_mb": round(m.get("size_vram", 0) / (1024**2), 0),
                    "processor": m.get("details", {}).get("processor", "CPU"),
                })
            if models:
                gpu_info["available"] = True
    except Exception:
        pass

    return gpu_info


# ── Metrik Toplama ──────────────────────────────────────────────

class MetricsCollector:
    """API ve sistem metriklerini toplar."""

    def __init__(self, max_samples: int = 10000):
        self._response_times: deque = deque(maxlen=max_samples)
        self._errors: deque = deque(maxlen=max_samples)
        self._requests: deque = deque(maxlen=max_samples)
        self._start_time = time.time()

    def record_request(self, endpoint: str, method: str, status_code: int, duration_ms: float):
        """API isteğini kaydet."""
        entry = {
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "timestamp": time.time(),
            "is_error": status_code >= 400,
        }
        self._requests.append(entry)
        self._response_times.append(duration_ms)

        if status_code >= 400:
            self._errors.append(entry)

    def get_response_time_stats(self, last_minutes: int = 60) -> Dict:
        """Yanıt süresi istatistikleri (percentile)."""
        cutoff = time.time() - (last_minutes * 60)
        times = [r for r in self._response_times if True]  # all samples

        if not times:
            return {"count": 0}

        sorted_times = sorted(times)
        n = len(sorted_times)

        return {
            "count": n,
            "avg_ms": round(sum(sorted_times) / n, 2),
            "min_ms": round(sorted_times[0], 2),
            "max_ms": round(sorted_times[-1], 2),
            "p50_ms": round(sorted_times[int(n * 0.5)], 2),
            "p90_ms": round(sorted_times[int(n * 0.9)], 2),
            "p95_ms": round(sorted_times[int(n * 0.95)], 2),
            "p99_ms": round(sorted_times[min(int(n * 0.99), n - 1)], 2),
        }

    def get_error_rate(self, last_minutes: int = 60) -> Dict:
        """Hata oranı (son N dakika)."""
        cutoff = time.time() - (last_minutes * 60)
        recent_requests = [r for r in self._requests if r["timestamp"] > cutoff]
        recent_errors = [r for r in recent_requests if r["is_error"]]

        total = len(recent_requests)
        errors = len(recent_errors)

        # Hata dağılımı
        error_codes = {}
        for e in recent_errors:
            code = str(e["status_code"])
            error_codes[code] = error_codes.get(code, 0) + 1

        return {
            "total_requests": total,
            "total_errors": errors,
            "error_rate_percent": round(errors / total * 100, 2) if total > 0 else 0,
            "error_distribution": error_codes,
            "period_minutes": last_minutes,
        }

    def get_throughput(self, last_minutes: int = 60) -> Dict:
        """İstek hacmi (throughput)."""
        cutoff = time.time() - (last_minutes * 60)
        recent = [r for r in self._requests if r["timestamp"] > cutoff]

        # Endpoint dağılımı
        endpoint_counts = {}
        for r in recent:
            ep = r["endpoint"]
            endpoint_counts[ep] = endpoint_counts.get(ep, 0) + 1

        return {
            "total_requests": len(recent),
            "requests_per_minute": round(len(recent) / max(last_minutes, 1), 2),
            "top_endpoints": dict(sorted(endpoint_counts.items(), key=lambda x: -x[1])[:10]),
            "period_minutes": last_minutes,
        }


# ── Uyarı Sistemi ──────────────────────────────────────────────

class AlertManager:
    """Threshold-based uyarı sistemi."""

    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_CRITICAL = "critical"

    DEFAULT_THRESHOLDS = {
        "cpu_warning": 80,
        "cpu_critical": 95,
        "memory_warning": 80,
        "memory_critical": 95,
        "disk_warning": 85,
        "disk_critical": 95,
        "error_rate_warning": 5,     # %5
        "error_rate_critical": 15,   # %15
        "response_time_warning": 5000,   # 5 saniye
        "response_time_critical": 30000, # 30 saniye
        "gpu_memory_warning": 85,
        "gpu_temp_warning": 80,
    }

    def __init__(self):
        self._alerts: List[Dict] = []
        self._thresholds = self.DEFAULT_THRESHOLDS.copy()
        self._load_alerts()

    def _load_alerts(self):
        data = {}
        if _ALERTS_FILE.exists():
            try:
                data = json.loads(_ALERTS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        self._alerts = data.get("alerts", [])
        if "thresholds" in data:
            self._thresholds.update(data["thresholds"])

    def _save_alerts(self):
        _ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _ALERTS_FILE.write_text(json.dumps({
            "alerts": self._alerts[-200:],
            "thresholds": self._thresholds,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    def fire_alert(self, category: str, message: str, severity: str, value: float = 0, threshold: float = 0):
        """Yeni uyarı oluştur."""
        alert = {
            "id": f"{category}_{int(time.time())}",
            "category": category,
            "message": message,
            "severity": severity,
            "value": value,
            "threshold": threshold,
            "timestamp": _utcnow_str(),
            "acknowledged": False,
        }
        self._alerts.append(alert)
        self._save_alerts()
        logger.warning("monitoring_alert", category=category, severity=severity, message=message)

    def check_system(self, metrics_collector: Optional['MetricsCollector'] = None) -> List[Dict]:
        """Sistem durumunu kontrol et ve gerekirse uyarı oluştur."""
        new_alerts = []

        if PSUTIL_AVAILABLE:
            # CPU
            cpu = psutil.cpu_percent(interval=1)
            if cpu >= self._thresholds["cpu_critical"]:
                self.fire_alert("cpu", f"CPU kullanımı kritik: %{cpu}", self.SEVERITY_CRITICAL, cpu, self._thresholds["cpu_critical"])
                new_alerts.append("cpu_critical")
            elif cpu >= self._thresholds["cpu_warning"]:
                self.fire_alert("cpu", f"CPU kullanımı yüksek: %{cpu}", self.SEVERITY_WARNING, cpu, self._thresholds["cpu_warning"])
                new_alerts.append("cpu_warning")

            # Memory
            mem = psutil.virtual_memory().percent
            if mem >= self._thresholds["memory_critical"]:
                self.fire_alert("memory", f"RAM kullanımı kritik: %{mem}", self.SEVERITY_CRITICAL, mem, self._thresholds["memory_critical"])
                new_alerts.append("memory_critical")
            elif mem >= self._thresholds["memory_warning"]:
                self.fire_alert("memory", f"RAM kullanımı yüksek: %{mem}", self.SEVERITY_WARNING, mem, self._thresholds["memory_warning"])
                new_alerts.append("memory_warning")

            # Disk
            disk = psutil.disk_usage("/").percent
            if disk >= self._thresholds["disk_critical"]:
                self.fire_alert("disk", f"Disk kullanımı kritik: %{disk}", self.SEVERITY_CRITICAL, disk, self._thresholds["disk_critical"])
                new_alerts.append("disk_critical")
            elif disk >= self._thresholds["disk_warning"]:
                self.fire_alert("disk", f"Disk kullanımı yüksek: %{disk}", self.SEVERITY_WARNING, disk, self._thresholds["disk_warning"])
                new_alerts.append("disk_warning")

        # GPU
        gpu_info = get_gpu_info()
        for gpu in gpu_info.get("gpus", []):
            if "temperature_c" in gpu and gpu["temperature_c"] >= self._thresholds["gpu_temp_warning"]:
                self.fire_alert("gpu_temp", f"GPU sıcaklığı yüksek: {gpu['temperature_c']}°C", self.SEVERITY_WARNING)
                new_alerts.append("gpu_temp")
            if "memory_utilization_percent" in gpu and gpu["memory_utilization_percent"] >= self._thresholds["gpu_memory_warning"]:
                self.fire_alert("gpu_memory", f"GPU bellek kullanımı yüksek: %{gpu['memory_utilization_percent']}", self.SEVERITY_WARNING)
                new_alerts.append("gpu_memory")

        # Error rate
        if metrics_collector:
            error_data = metrics_collector.get_error_rate(last_minutes=15)
            er = error_data["error_rate_percent"]
            if er >= self._thresholds["error_rate_critical"]:
                self.fire_alert("error_rate", f"Hata oranı kritik: %{er}", self.SEVERITY_CRITICAL, er, self._thresholds["error_rate_critical"])
                new_alerts.append("error_rate_critical")
            elif er >= self._thresholds["error_rate_warning"]:
                self.fire_alert("error_rate", f"Hata oranı yüksek: %{er}", self.SEVERITY_WARNING, er, self._thresholds["error_rate_warning"])
                new_alerts.append("error_rate_warning")

        return new_alerts

    def acknowledge_alert(self, alert_id: str):
        """Uyarıyı onayla (acknowledged)."""
        for a in self._alerts:
            if a["id"] == alert_id:
                a["acknowledged"] = True
                self._save_alerts()
                return True
        return False

    def get_active_alerts(self, severity: Optional[str] = None) -> List[Dict]:
        """Onaylanmamış aktif uyarıları döndür."""
        active = [a for a in self._alerts if not a["acknowledged"]]
        if severity:
            active = [a for a in active if a["severity"] == severity]
        return active[-50:]

    def get_all_alerts(self, limit: int = 100) -> List[Dict]:
        """Tüm uyarıları döndür."""
        return self._alerts[-limit:]


# ── Sağlık Puanı ────────────────────────────────────────────────

def calculate_health_score() -> Dict:
    """0-100 arası sistem sağlık puanı hesapla."""
    score = 100
    details = {}

    if PSUTIL_AVAILABLE:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent

        # CPU (maks -25 puan)
        if cpu > 90:
            score -= 25
        elif cpu > 70:
            score -= 15
        elif cpu > 50:
            score -= 5
        details["cpu_percent"] = cpu

        # RAM (maks -25 puan)
        if mem > 90:
            score -= 25
        elif mem > 70:
            score -= 15
        elif mem > 50:
            score -= 5
        details["memory_percent"] = mem

        # Disk (maks -20 puan)
        if disk > 90:
            score -= 20
        elif disk > 70:
            score -= 10
        details["disk_percent"] = disk

    # LLM durumu (maks -20 puan)
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            details["llm_status"] = "active"
        else:
            score -= 20
            details["llm_status"] = "error"
    except Exception:
        score -= 20
        details["llm_status"] = "unreachable"

    # GPU (bonus +10)
    gpu = get_gpu_info()
    if gpu["available"]:
        details["gpu_available"] = True
        score = min(100, score + 5)
    else:
        details["gpu_available"] = False

    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"

    return {
        "score": max(0, score),
        "grade": grade,
        "details": details,
        "timestamp": _utcnow_str(),
    }


def get_full_telemetry(metrics_collector: Optional['MetricsCollector'] = None) -> Dict:
    """Tam telemetri raporu."""
    result = {
        "health": calculate_health_score(),
        "gpu": get_gpu_info(),
        "timestamp": _utcnow_str(),
    }

    if PSUTIL_AVAILABLE:
        result["system"] = {
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "cpu_count": psutil.cpu_count(),
            "memory": {
                "total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
                "used_gb": round(psutil.virtual_memory().used / (1024**3), 1),
                "percent": psutil.virtual_memory().percent,
            },
            "disk": {
                "total_gb": round(psutil.disk_usage("/").total / (1024**3), 1),
                "used_gb": round(psutil.disk_usage("/").used / (1024**3), 1),
                "percent": psutil.disk_usage("/").percent,
            },
            "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
        }

    if metrics_collector:
        result["api"] = {
            "response_times": metrics_collector.get_response_time_stats(),
            "error_rate": metrics_collector.get_error_rate(),
            "throughput": metrics_collector.get_throughput(),
        }

    return result


# Singleton instances
metrics_collector = MetricsCollector()
alert_manager = AlertManager()

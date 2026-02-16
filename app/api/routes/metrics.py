"""
CompanyAI — Prometheus Metrics Endpoint
==========================================
/api/metrics endpoint'i — Prometheus scraping uyumlu.
Toplanan metrikler: istek sayısı, yanıt süresi, öğrenme stats.
"""

import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["Monitoring"])

# ── In-memory Metrikler (process başına) ──
# Not: Multi-worker'da her worker kendi metrikleri tutar.
# Tam çözüm için prometheus_client kütüphanesi kullanılabilir.

_metrics = {
    "requests_total": 0,
    "requests_by_status": defaultdict(int),  # status_code → count
    "requests_by_path": defaultdict(int),    # path → count
    "response_time_sum": 0.0,               # toplam süre (saniye)
    "response_time_count": 0,               # sayaç
    "errors_total": 0,
    "startup_time": time.time(),
}


def record_request(path: str, status_code: int, duration: float):
    """Bir isteğin metriklerini kaydet (middleware'den çağrılır)."""
    _metrics["requests_total"] += 1
    _metrics["requests_by_status"][status_code] += 1
    _metrics["requests_by_path"][path] += 1
    _metrics["response_time_sum"] += duration
    _metrics["response_time_count"] += 1
    if status_code >= 500:
        _metrics["errors_total"] += 1


def _format_prometheus(metrics: dict) -> str:
    """Metrikleri Prometheus text format'a çevir."""
    lines = []

    # Uptime
    uptime = time.time() - metrics["startup_time"]
    lines.append(f"# HELP companyai_uptime_seconds Server uptime in seconds")
    lines.append(f"# TYPE companyai_uptime_seconds gauge")
    lines.append(f"companyai_uptime_seconds {uptime:.2f}")

    # Toplam istek
    lines.append(f"# HELP companyai_requests_total Total HTTP requests")
    lines.append(f"# TYPE companyai_requests_total counter")
    lines.append(f'companyai_requests_total {metrics["requests_total"]}')

    # Status code bazlı
    lines.append(f"# HELP companyai_requests_by_status HTTP requests by status code")
    lines.append(f"# TYPE companyai_requests_by_status counter")
    for code, count in sorted(metrics["requests_by_status"].items()):
        lines.append(f'companyai_requests_by_status{{status="{code}"}} {count}')

    # Hata sayısı
    lines.append(f"# HELP companyai_errors_total Total 5xx errors")
    lines.append(f"# TYPE companyai_errors_total counter")
    lines.append(f'companyai_errors_total {metrics["errors_total"]}')

    # Ortalama yanıt süresi
    avg_time = (
        metrics["response_time_sum"] / metrics["response_time_count"]
        if metrics["response_time_count"] > 0
        else 0
    )
    lines.append(f"# HELP companyai_response_time_avg_seconds Average response time")
    lines.append(f"# TYPE companyai_response_time_avg_seconds gauge")
    lines.append(f"companyai_response_time_avg_seconds {avg_time:.4f}")

    # En çok istek alan endpoint'ler (top 10)
    lines.append(f"# HELP companyai_requests_by_path HTTP requests by path")
    lines.append(f"# TYPE companyai_requests_by_path counter")
    top_paths = sorted(metrics["requests_by_path"].items(), key=lambda x: -x[1])[:10]
    for path, count in top_paths:
        safe_path = path.replace('"', '\\"')
        lines.append(f'companyai_requests_by_path{{path="{safe_path}"}} {count}')

    return "\n".join(lines) + "\n"


@router.get("/metrics", response_class=Response)
async def prometheus_metrics():
    """
    Prometheus uyumlu metrik endpoint'i.
    
    Scrape config:
      - job_name: 'companyai'
        static_configs:
          - targets: ['192.168.0.12:8000']
        metrics_path: '/api/metrics'
    """
    body = _format_prometheus(_metrics)
    return Response(content=body, media_type="text/plain; charset=utf-8")


@router.get("/metrics/json")
async def metrics_json():
    """JSON formatında metrikler (admin dashboard için)."""
    uptime = time.time() - _metrics["startup_time"]
    avg_time = (
        _metrics["response_time_sum"] / _metrics["response_time_count"]
        if _metrics["response_time_count"] > 0
        else 0
    )

    # ChromaDB istatistikleri
    chroma_stats = {}
    try:
        from app.rag.vector_store import get_stats
        chroma_stats = get_stats()
    except Exception:
        chroma_stats = {"available": False}

    return {
        "uptime_seconds": round(uptime, 2),
        "requests_total": _metrics["requests_total"],
        "errors_total": _metrics["errors_total"],
        "avg_response_time_ms": round(avg_time * 1000, 2),
        "requests_by_status": dict(_metrics["requests_by_status"]),
        "top_paths": dict(
            sorted(_metrics["requests_by_path"].items(), key=lambda x: -x[1])[:10]
        ),
        "chromadb": chroma_stats,
    }


# ══════════════════════════════════════════════════════════════
# v4.4.0: Öğrenme Dashboard API
# ══════════════════════════════════════════════════════════════

@router.get("/metrics/learning")
async def learning_dashboard():
    """Öğrenme ve RAG kalitesi dashboard'u.
    
    Döndürülen veriler:
    - Koleksiyonlardaki doküman sayıları
    - Retrieval kalite metrikleri (avg score, MRR, latency)
    - Son 10 aramanın detayları
    """
    dashboard = {
        "collections": {},
        "retrieval_quality": {},
        "knowledge_extractor": {},
    }
    
    # 1. Koleksiyon istatistikleri
    try:
        from app.rag.vector_store import get_stats
        dashboard["collections"] = get_stats()
    except Exception as e:
        dashboard["collections"] = {"error": str(e)}

    # 2. Retrieval metrikleri
    try:
        from app.rag.vector_store import get_retrieval_metrics_summary
        dashboard["retrieval_quality"] = get_retrieval_metrics_summary()
    except Exception as e:
        dashboard["retrieval_quality"] = {"error": str(e)}
    
    # 3. Öğrenme kalite bilgisi
    try:
        from app.core.knowledge_extractor import MIN_QUALITY_SCORE
        dashboard["knowledge_extractor"] = {
            "min_quality_threshold": MIN_QUALITY_SCORE,
            "status": "active",
        }
    except Exception:
        dashboard["knowledge_extractor"] = {"status": "unavailable"}
    
    return dashboard

"""
CompanyAI — Gunicorn Production Yapılandırması
=================================================
Tek uvicorn worker yerine multi-worker production setup.

Kullanım:
  gunicorn app.main:app -c gunicorn.conf.py
"""

import multiprocessing
import os

# ── Worker Sayısı ──
# CPU-bound LLM inference — fazla worker gereksiz, 4 yeterli
workers = min(4, multiprocessing.cpu_count())

# Uvicorn worker (async desteği için)
worker_class = "uvicorn.workers.UvicornWorker"

# ── Bağlantı Ayarları ──
bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '8000')}"
backlog = 2048

# ── Timeout ──
# v4.5.0: 960s → 180s — DoS vektörü kapatıldı
# Uzun süreli LLM işlemleri SSE streaming ile ayrı handle edilir
timeout = 180       # Worker timeout (makul üst sınır)
graceful_timeout = 30
keepalive = 5

# ── Logging ──
accesslog = "-"                  # stdout'a yaz
errorlog = "-"                   # stderr'e yaz
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# ── Process Adı ──
proc_name = "companyai"

# ── Güvenlik ──
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# ── Worker Lifecycle ──
max_requests = 1000              # Memory leak koruması: N istekten sonra worker yeniden başlat
max_requests_jitter = 50         # Aynı anda restart engellemek için jitter

# ── Preload ──
preload_app = False              # Her worker kendi app instance'ı (DB connection pool paylaşım sorunu)

# ── Hooks ──
def on_starting(server):
    """Gunicorn başlarken çalışır."""
    pass

def post_fork(server, worker):
    """Her worker fork sonrası."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def pre_exec(server):
    """Graceful restart öncesi."""
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    """Tüm worker'lar hazır."""
    server.log.info("Server is ready. Spawning workers")

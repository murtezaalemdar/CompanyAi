"""
Kurumsal AI Asistanı - FastAPI Ana Uygulama

Local LLM (GPT-OSS-20B) + Öğrenen Vektör Hafıza + JWT Auth
"""
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from app.config import settings
from app.config import APP_VERSION
from app.db.database import engine, init_db
from app.db.models import Base
from app.api.routes import auth, ask, admin, documents, multimodal, memory, analyze, export, backup, metrics

# Rate Limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"])
    RATE_LIMIT_AVAILABLE = True
except ImportError:
    limiter = None
    RATE_LIMIT_AVAILABLE = False

# Structured logging yapılandırması
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()


# ── Correlation ID Middleware ──
class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Her isteğe benzersiz request_id atar — log tracking için"""
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── Metrics Middleware ──
class MetricsMiddleware(BaseHTTPMiddleware):
    """Her isteğin süresini ve durumunu metrik olarak kaydet"""
    async def dispatch(self, request: Request, call_next):
        import time as _time
        start = _time.time()
        response = await call_next(request)
        duration = _time.time() - start
        try:
            from app.api.routes.metrics import record_request
            path = request.url.path
            record_request(path, response.status_code, duration)
        except Exception:
            pass
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlangıç ve kapanış işlemleri"""
    logger.info("app_starting", version=APP_VERSION)
    
    # ── GPU Otomatik Algılama ──
    from app.llm.gpu_config import gpu_config
    await gpu_config.probe()
    logger.info("gpu_probe_complete", mode=gpu_config.mode,
                gpu_count=gpu_config.gpu_count,
                total_vram_gb=gpu_config.total_vram_gb)
    
    # Veritabanı tablolarını oluştur
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("database_initialized")
    
    # ── Aktif Model Katman Sayısını Algıla ──
    from app.api.routes.admin import _detect_model_layers, _TOTAL_MODEL_LAYERS
    import app.api.routes.admin as _admin_mod
    try:
        _layers, _model = await _detect_model_layers()
        if _layers > 0:
            _admin_mod._TOTAL_MODEL_LAYERS = _layers
            _admin_mod._ACTIVE_MODEL_NAME = _model
            logger.info("model_layers_detected",
                        model=_model, layers=_layers)
        else:
            logger.info("model_layers_default",
                        model=_model or "unknown",
                        layers=_admin_mod._TOTAL_MODEL_LAYERS)
    except Exception as e:
        logger.warning("model_layer_detect_startup_failed", error=str(e))

    # ── Kayıtlı Performans Profilini Geri Yükle ──
    from app.db.database import async_session_maker
    from app.db.models import User, SystemSettings
    from app.auth.jwt_handler import hash_password
    from sqlalchemy import select
    import json as _json

    async with async_session_maker() as session:
        try:
            result = await session.execute(
                select(SystemSettings).where(SystemSettings.key == "performance_profile")
            )
            perf_setting = result.scalar_one_or_none()
            if perf_setting and perf_setting.value:
                _profile = _json.loads(perf_setting.value)
                _mode = _profile.get("mode", "auto")
                if _mode != "auto":
                    from app.api.routes.admin import _calc_perf_params
                    _params = _calc_perf_params(
                        _profile.get("gpu_percent", 100),
                        _profile.get("cpu_percent", 100),
                        _profile.get("ram_percent", 100),
                    )
                    gpu_config.num_gpu = _params["num_gpu"]
                    gpu_config.num_thread = _params["num_thread"]
                    gpu_config.num_ctx = _params["num_ctx"]
                    gpu_config.num_batch = _params["num_batch"]
                    logger.info("performance_profile_restored",
                                mode=_mode,
                                gpu_pct=_profile.get("gpu_percent"),
                                cpu_pct=_profile.get("cpu_percent"),
                                ram_pct=_profile.get("ram_percent"))
        except Exception as e:
            logger.warning("performance_profile_restore_failed", error=str(e))
    
    # Admin kullanıcısını kontrol et ve oluştur
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == "admin@company.ai"))
        admin_user = result.scalar_one_or_none()
        
        if not admin_user:
            logger.info("creating_admin_user")
            admin_user = User(
                email="admin@company.ai",
                hashed_password=hash_password(settings.ADMIN_DEFAULT_PASSWORD),
                full_name="System Admin",
                role="admin",
                is_active=True,
                must_change_password=True,
            )
            session.add(admin_user)
            await session.commit()
            logger.info("admin_user_created", email="admin@company.ai")
        else:
            logger.info("admin_user_exists")

    # ── Periyodik Donanım Tarama Görevi (her 5 dk) ──
    import asyncio

    async def _hardware_monitor():
        """Arka planda donanım + model değişikliklerini algıla."""
        while True:
            await asyncio.sleep(300)  # 5 dakika
            try:
                old_gpu_count = gpu_config.gpu_count
                old_vram = gpu_config.total_vram_gb
                old_mode = gpu_config.mode
                old_model = _admin_mod._ACTIVE_MODEL_NAME
                old_layers = _admin_mod._TOTAL_MODEL_LAYERS

                await gpu_config.probe()

                # ── Model değişikliği kontrolü ──
                _new_layers, _new_model = await _detect_model_layers()
                model_changed = False
                if _new_model and _new_model != old_model:
                    model_changed = True
                if _new_layers > 0 and _new_layers != old_layers:
                    model_changed = True

                if model_changed and _new_layers > 0:
                    _admin_mod._TOTAL_MODEL_LAYERS = _new_layers
                    _admin_mod._ACTIVE_MODEL_NAME = _new_model
                    logger.info(
                        "model_change_detected",
                        old_model=old_model,
                        new_model=_new_model,
                        old_layers=old_layers,
                        new_layers=_new_layers,
                    )

                hw_changed = (
                    gpu_config.gpu_count != old_gpu_count or
                    abs(gpu_config.total_vram_gb - old_vram) > 0.5
                )

                if hw_changed or model_changed:
                    if hw_changed:
                        logger.info(
                            "hardware_change_detected",
                            old_gpu_count=old_gpu_count,
                            new_gpu_count=gpu_config.gpu_count,
                            old_vram_gb=old_vram,
                            new_vram_gb=gpu_config.total_vram_gb,
                            old_mode=old_mode,
                            new_mode=gpu_config.mode,
                        )
                    # Kayıtlı profili tekrar uygula (yeni layer sayısıyla)
                    async with async_session_maker() as session:
                        result = await session.execute(
                            select(SystemSettings).where(
                                SystemSettings.key == "performance_profile"
                            )
                        )
                        perf = result.scalar_one_or_none()
                        if perf and perf.value:
                            _p = _json.loads(perf.value)
                            if _p.get("mode", "auto") != "auto":
                                from app.api.routes.admin import _calc_perf_params
                                _params = _calc_perf_params(
                                    _p.get("gpu_percent", 100),
                                    _p.get("cpu_percent", 100),
                                    _p.get("ram_percent", 100),
                                )
                                gpu_config.num_gpu = _params["num_gpu"]
                                gpu_config.num_thread = _params["num_thread"]
                                gpu_config.num_ctx = _params["num_ctx"]
                                gpu_config.num_batch = _params["num_batch"]
                    # HTTP client'ı yenile
                    from app.llm.client import ollama_client
                    await ollama_client._refresh_client_if_needed()
            except Exception as e:
                logger.warning("hardware_monitor_error", error=str(e))

    hw_task = asyncio.create_task(_hardware_monitor())

    yield
    
    # Shutdown — kaynakları temizle
    logger.info("app_shutting_down")
    hw_task.cancel()
    from app.llm.client import ollama_client
    await ollama_client.close()
    await engine.dispose()


# FastAPI uygulaması
app = FastAPI(
    title="Kurumsal AI Asistanı",
    description="Local LLM tabanlı kurumsal yapay zeka asistanı",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# ── Middleware'lar ──

# Correlation ID (en dışta — her isteğe ID atar)
app.add_middleware(CorrelationIDMiddleware)

# Metrics (her isteğin süresini kaydet)
app.add_middleware(MetricsMiddleware)

# CORS middleware — sıkılaştırılmış (v4.5.0)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization", "Content-Type", "Accept", "Origin",
        "X-Request-ID", "X-Requested-With",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

# Rate Limiting
if RATE_LIMIT_AVAILABLE and limiter:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Merkezi Error Handler ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Yakalanmamış hataları loglayıp güvenli JSON döner"""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=str(request.url.path),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Sunucu hatası oluştu",
            "request_id": request_id,
        },
    )

# Router'ları ekle
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(ask.router, prefix="/api", tags=["AI Assistant"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory Management"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(documents.router, prefix="/api/rag", tags=["RAG Documents"])
app.include_router(multimodal.router, prefix="/api", tags=["Multimodal AI"])
app.include_router(analyze.router, prefix="/api/analyze", tags=["Document Analysis"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(backup.router, prefix="/api/backup", tags=["Backup & Restore"])
app.include_router(metrics.router, prefix="/api", tags=["Monitoring"])


@app.get("/")
async def root():
    """API ana sayfa"""
    return {
        "name": "Kurumsal AI Asistanı",
        "version": APP_VERSION,
        "status": "running",
        "docs": "/docs" if settings.DEBUG else "Disabled in production",
    }


@app.get("/api/health")
async def health():
    """Gelişmiş sağlık kontrolü — DB, LLM, ChromaDB durumu"""
    from app.llm.client import ollama_client
    
    checks = {"status": "healthy", "version": APP_VERSION}
    
    # DB kontrolü
    try:
        from app.db.database import async_session_maker
        from sqlalchemy import text
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception:
        checks["database"] = "disconnected"
        checks["status"] = "degraded"
    
    # LLM kontrolü
    try:
        checks["llm"] = "available" if await ollama_client.is_available() else "unavailable"
    except Exception:
        checks["llm"] = "unavailable"
    
    return checks


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

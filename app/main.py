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
from app.db.database import engine, init_db
from app.db.models import Base
from app.api.routes import auth, ask, admin, documents, multimodal, memory, analyze, export

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlangıç ve kapanış işlemleri"""
    logger.info("app_starting", version="2.0.0")
    
    # Veritabanı tablolarını oluştur
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("database_initialized")
    
    # Admin kullanıcısını kontrol et ve oluştur
    from app.db.database import async_session_maker
    from app.db.models import User
    from app.auth.jwt_handler import hash_password
    from sqlalchemy import select
    
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
            )
            session.add(admin_user)
            await session.commit()
            logger.info("admin_user_created", email="admin@company.ai")
        else:
            logger.info("admin_user_exists")

    yield
    
    # Shutdown — kaynakları temizle
    logger.info("app_shutting_down")
    from app.llm.client import ollama_client
    await ollama_client.close()
    await engine.dispose()


# FastAPI uygulaması
app = FastAPI(
    title="Kurumsal AI Asistanı",
    description="Local LLM tabanlı kurumsal yapay zeka asistanı",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# ── Middleware'lar ──

# Correlation ID (en dışta — her isteğe ID atar)
app.add_middleware(CorrelationIDMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/")
async def root():
    """API ana sayfa"""
    return {
        "name": "Kurumsal AI Asistanı",
        "version": "2.1.0",
        "status": "running",
        "docs": "/docs" if settings.DEBUG else "Disabled in production",
    }


@app.get("/api/health")
async def health():
    """Gelişmiş sağlık kontrolü — DB, LLM, ChromaDB durumu"""
    from app.llm.client import ollama_client
    
    checks = {"status": "healthy"}
    
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

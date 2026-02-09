"""
Kurumsal AI Asistanı - FastAPI Ana Uygulama

Local LLM (Mistral) + Öğrenen Vektör Hafıza + JWT Auth
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import settings
from app.db.database import engine, init_db
from app.db.models import Base
from app.api.routes import auth, ask, admin, documents, multimodal, memory

# Structured logging yapılandırması
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()


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
                hashed_password=hash_password("admin123"),
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
    
    # Shutdown
    logger.info("app_shutting_down")
    await engine.dispose()


# FastAPI uygulaması
app = FastAPI(
    title="Kurumsal AI Asistanı",
    description="Local LLM tabanlı kurumsal yapay zeka asistanı",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları ekle
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(ask.router, prefix="/api", tags=["AI Assistant"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory Management"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(documents.router, prefix="/api/rag", tags=["RAG Documents"])
app.include_router(multimodal.router, prefix="/api", tags=["Multimodal AI"])


@app.get("/")
async def root():
    """API ana sayfa"""
    return {
        "name": "Kurumsal AI Asistanı",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs" if settings.DEBUG else "Disabled in production",
    }


@app.get("/api/health")
async def health():
    """Sağlık kontrolü endpoint'i"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

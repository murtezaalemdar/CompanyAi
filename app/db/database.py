"""PostgreSQL Veritabanı Bağlantısı"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# Async engine oluştur
# Async engine oluştur
engine_args = {
    "echo": settings.DEBUG,
}

if "sqlite" in settings.DATABASE_URL:
    from sqlalchemy.pool import StaticPool
    engine_args.update({
        "connect_args": {"check_same_thread": False}, 
        "poolclass": StaticPool
    })
else:
    engine_args.update({
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    })

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_args
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    FastAPI dependency: Veritabanı session'ı sağlar.
    
    Kullanım:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Veritabanı tablolarını oluşturur (development için)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

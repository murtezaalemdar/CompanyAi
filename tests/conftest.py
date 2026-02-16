"""
CompanyAI — Test Fixtures & Configuration
==========================================
Tüm testlerin kullandığı ortak fixture'lar burada tanımlıdır.
SQLite in-memory DB, fake HTTP client, mock ChromaDB vb.
"""

import os
import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ── Test ortamı env değişkenleri (import'lardan ÖNCE ayarlanmalı) ──
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-very-long-string-for-testing-only"
os.environ["DEBUG"] = "true"
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
os.environ["LLM_MODEL"] = "test-model"
os.environ["ADMIN_DEFAULT_PASSWORD"] = "testpass123"
os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'

# Proje kökünü path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Event Loop Fixture ──
@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Database Fixtures ──
@pytest_asyncio.fixture
async def db_engine():
    """In-memory SQLite async engine for testing."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    from app.db.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Async database session for testing (auto-rollback)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    session_maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session
        await session.rollback()


# ── Auth Fixtures ──
@pytest.fixture
def test_user_data():
    """Standard test user data."""
    return {
        "email": "test@company.ai",
        "password": "securepass123",
        "full_name": "Test User",
        "department": "IT",
        "role": "user",
    }


@pytest.fixture
def admin_user_data():
    """Admin test user data."""
    return {
        "email": "admin@company.ai",
        "password": "adminpass123",
        "full_name": "Admin User",
        "department": "Yönetim",
        "role": "admin",
    }


@pytest.fixture
def access_token(test_user_data):
    """Valid JWT access token for testing."""
    from app.auth.jwt_handler import create_access_token
    return create_access_token({"sub": test_user_data["email"], "role": "user"})


@pytest.fixture
def admin_token(admin_user_data):
    """Valid JWT admin token for testing."""
    from app.auth.jwt_handler import create_access_token
    return create_access_token({"sub": admin_user_data["email"], "role": "admin"})


# ── FastAPI Test Client ──
@pytest_asyncio.fixture
async def app():
    """FastAPI app instance for testing."""
    from app.main import app as fastapi_app
    yield fastapi_app


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP test client."""
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Mock Fixtures ──
@pytest.fixture
def mock_ollama():
    """Mock Ollama LLM client."""
    with patch("app.llm.client.OllamaClient") as mock:
        instance = mock.return_value
        instance.generate = AsyncMock(return_value="Bu bir test yanıtıdır.")
        instance.stream = AsyncMock()
        instance.is_available = AsyncMock(return_value=True)
        instance.close = AsyncMock()
        yield instance


@pytest.fixture
def mock_chromadb():
    """Mock ChromaDB collection."""
    collection = MagicMock()
    collection.add = MagicMock()
    collection.query = MagicMock(return_value={
        "documents": [["Test doküman içeriği"]],
        "metadatas": [[{"source": "test.txt", "type": "text"}]],
        "distances": [[0.3]],
        "ids": [["test_0"]],
    })
    collection.count = MagicMock(return_value=10)
    collection.get = MagicMock(return_value={"ids": [], "metadatas": []})
    return collection


@pytest.fixture
def mock_embedding_model():
    """Mock SentenceTransformer model."""
    import numpy as np
    model = MagicMock()
    model.encode = MagicMock(return_value=np.random.rand(768).astype("float32"))
    return model

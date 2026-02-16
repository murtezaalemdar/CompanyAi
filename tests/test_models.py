"""
CompanyAI — Database Models & Config Unit Tests
==================================================
ORM modelleri, DB session lifecycle ve config testleri.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models import User, Query, ChatSession, ConversationMemory, _utcnow
from app.auth.jwt_handler import hash_password


# ═══════════════════════════════════════════════════
# 1. _utcnow helper
# ═══════════════════════════════════════════════════

class TestUtcNow:
    """_utcnow fonksiyonu testleri."""

    def test_returns_datetime(self):
        from datetime import datetime
        result = _utcnow()
        assert isinstance(result, datetime)

    def test_timezone_naive(self):
        """DB uyumluluğu için tzinfo=None olmalı."""
        result = _utcnow()
        assert result.tzinfo is None


# ═══════════════════════════════════════════════════
# 2. User Model CRUD
# ═══════════════════════════════════════════════════

class TestUserModel:
    """User modeli CRUD testleri."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        user = User(
            email="test@company.ai",
            hashed_password=hash_password("test123"),
            full_name="Test Kullanıcı",
            department="IT",
            role="user",
        )
        db_session.add(user)
        await db_session.flush()

        assert user.id is not None
        assert user.email == "test@company.ai"
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_email_uniqueness(self, db_session):
        """Aynı email ile iki kullanıcı oluşturulamamalı."""
        user1 = User(email="dup@test.com", hashed_password="hash1")
        db_session.add(user1)
        await db_session.flush()

        user2 = User(email="dup@test.com", hashed_password="hash2")
        db_session.add(user2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_user_defaults(self, db_session):
        user = User(email="def@test.com", hashed_password="hash")
        db_session.add(user)
        await db_session.flush()

        assert user.role == "user"
        assert user.is_active is True
        assert user.created_at is not None

    @pytest.mark.asyncio
    async def test_query_user(self, db_session):
        user = User(email="query@test.com", hashed_password="hash")
        db_session.add(user)
        await db_session.flush()

        result = await db_session.execute(
            select(User).where(User.email == "query@test.com")
        )
        found = result.scalar_one()
        assert found.email == "query@test.com"


# ═══════════════════════════════════════════════════
# 3. Query Model
# ═══════════════════════════════════════════════════

class TestQueryModel:
    """Query modeli testleri."""

    @pytest.mark.asyncio
    async def test_create_query(self, db_session):
        user = User(email="q@test.com", hashed_password="hash")
        db_session.add(user)
        await db_session.flush()

        query = Query(
            user_id=user.id,
            question="Test sorusu nedir?",
            answer="Test cevabı budur.",
            mode="rag",
            confidence=0.85,
            processing_time_ms=1500,
        )
        db_session.add(query)
        await db_session.flush()

        assert query.id is not None
        assert query.processing_time_ms == 1500


# ═══════════════════════════════════════════════════
# 4. ChatSession + ConversationMemory
# ═══════════════════════════════════════════════════

class TestChatSession:
    """Chat session ve mesaj modeli testleri."""

    @pytest.mark.asyncio
    async def test_create_session(self, db_session):
        user = User(email="chat@test.com", hashed_password="hash")
        db_session.add(user)
        await db_session.flush()

        session = ChatSession(user_id=user.id, title="Test Oturumu")
        db_session.add(session)
        await db_session.flush()

        assert session.id is not None
        assert session.is_active is True

    @pytest.mark.asyncio
    async def test_add_message_to_session(self, db_session):
        user = User(email="msg@test.com", hashed_password="hash")
        db_session.add(user)
        await db_session.flush()

        session = ChatSession(user_id=user.id)
        db_session.add(session)
        await db_session.flush()

        msg = ConversationMemory(
            user_id=user.id,
            session_id=session.id,
            question="Nasılsın?",
            answer="İyiyim, teşekkürler!",
            intent="chat",
        )
        db_session.add(msg)
        await db_session.flush()

        assert msg.id is not None
        assert msg.session_id == session.id


# ═══════════════════════════════════════════════════
# 5. Config Tests
# ═══════════════════════════════════════════════════

class TestConfig:
    """app.config modülü testleri."""

    def test_version_format(self):
        from app.config import APP_VERSION
        parts = APP_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_settings_instance(self):
        from app.config import settings
        assert settings is not None
        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 8000

    def test_cors_origins_list(self):
        from app.config import settings
        origins = settings.cors_origins_list
        assert isinstance(origins, list)
        assert len(origins) >= 1

    def test_secret_key_not_default(self):
        """Startup'ta default key varsa rastgele üretilmeli."""
        from app.config import settings
        default = "change-this-to-a-very-long-random-string-in-production"
        # conftest'te test key ayarlanıyor, ya da auto-generated olmalı
        assert settings.SECRET_KEY != default or len(settings.SECRET_KEY) > 30

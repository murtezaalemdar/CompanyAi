"""
CompanyAI — JWT Handler Unit Tests
====================================
Token oluşturma, doğrulama, şifre hash/verify roundtrip testleri.
"""

import time
from datetime import timedelta

import pytest
from app.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
    hash_password,
    verify_password,
)


class TestCreateAccessToken:
    """Access token oluşturma testleri."""

    def test_creates_valid_token(self):
        token = create_access_token({"sub": "user@test.com"})
        assert isinstance(token, str)
        assert len(token) > 20

    def test_token_contains_user_data(self):
        data = {"sub": "user@test.com", "role": "admin"}
        token = create_access_token(data)
        payload = verify_token(token)
        assert payload["sub"] == "user@test.com"
        assert payload["role"] == "admin"

    def test_token_has_type_access(self):
        token = create_access_token({"sub": "x"})
        payload = verify_token(token)
        assert payload["type"] == "access"

    def test_custom_expiry(self):
        token = create_access_token({"sub": "x"}, expires_delta=timedelta(hours=2))
        payload = verify_token(token)
        assert payload is not None

    def test_expired_token_returns_none(self):
        token = create_access_token({"sub": "x"}, expires_delta=timedelta(seconds=-1))
        result = verify_token(token)
        assert result is None


class TestCreateRefreshToken:
    """Refresh token oluşturma testleri."""

    def test_creates_valid_refresh_token(self):
        token = create_refresh_token({"sub": "user@test.com"})
        assert isinstance(token, str)

    def test_refresh_token_has_type_refresh(self):
        token = create_refresh_token({"sub": "x"})
        payload = verify_token(token, token_type="refresh")
        assert payload["type"] == "refresh"

    def test_refresh_token_rejected_as_access(self):
        """Refresh token'ı access olarak kullanmak engellenmelidir."""
        token = create_refresh_token({"sub": "x"})
        result = verify_token(token, token_type="access")
        assert result is None


class TestVerifyToken:
    """Token doğrulama testleri."""

    def test_valid_token_returns_payload(self):
        token = create_access_token({"sub": "test@company.ai"})
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "test@company.ai"

    def test_garbage_token_returns_none(self):
        assert verify_token("not.a.valid.token") is None

    def test_empty_token_returns_none(self):
        assert verify_token("") is None

    def test_wrong_token_type_returns_none(self):
        """Access token'ı refresh olarak doğrulamak engellenmeli."""
        access = create_access_token({"sub": "x"})
        result = verify_token(access, token_type="refresh")
        assert result is None


class TestPasswordHashing:
    """Şifre hash ve doğrulama testleri."""

    def test_hash_password_returns_hash(self):
        hashed = hash_password("mypassword")
        assert hashed != "mypassword"
        assert len(hashed) > 20

    def test_verify_password_correct(self):
        hashed = hash_password("securepass123")
        assert verify_password("securepass123", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("securepass123")
        assert verify_password("wrongpass", hashed) is False

    def test_same_password_different_hashes(self):
        """Aynı şifre farklı hash'ler üretmeli (salt)."""
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2

    def test_empty_password_still_works(self):
        """Boş şifre bile hash'lenebilmeli (policy layer'da engellenir)."""
        hashed = hash_password("")
        assert verify_password("", hashed) is True

    def test_unicode_password(self):
        """Türkçe karakter içeren şifre."""
        hashed = hash_password("güçlüŞifre123")
        assert verify_password("güçlüŞifre123", hashed) is True

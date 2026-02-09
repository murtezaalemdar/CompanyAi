"""JWT Token İşlemleri"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT access token oluşturur."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """JWT refresh token oluşturur (uzun ömürlü)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """JWT token doğrular ve decode eder."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # Token tipi kontrolü (refresh token ile access endpoint'e erişim engellenir)
        if payload.get("type", "access") != token_type:
            return None
        return payload
    except JWTError:
        return None


def hash_password(password: str) -> str:
    """Şifreyi bcrypt ile hashler"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Şifre doğrulama"""
    return pwd_context.verify(plain_password, hashed_password)

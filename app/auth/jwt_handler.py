"""JWT Token İşlemleri"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT access token oluşturur.
    
    Args:
        data: Token'a eklenecek veri (genellikle user_id ve role)
        expires_delta: Token geçerlilik süresi
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    JWT token doğrular ve decode eder.
    
    Args:
        token: Doğrulanacak JWT token
    
    Returns:
        Token içindeki data veya None (geçersiz token)
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def hash_password(password: str) -> str:
    """Şifreyi bcrypt ile hashler"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Şifre doğrulama"""
    return pwd_context.verify(plain_password, hashed_password)

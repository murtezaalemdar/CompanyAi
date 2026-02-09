"""Authentication API Routes"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr

from app.db.database import get_db
from app.db.models import User
from app.auth.jwt_handler import (
    create_access_token,
    verify_token,
    hash_password,
    verify_password,
)
from app.core.audit import log_action
from app.config import settings

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# Pydantic schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str
    is_active: bool
    department: str | None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int | None = None
    role: str | None = None


# Dependency: Mevcut kullanıcıyı al
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT token'dan mevcut kullanıcıyı döner"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz kimlik bilgileri",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Hesap devre dışı")
    
    return user


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Yeni kullanıcı kaydı"""
    # Email kontrolü
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu email zaten kayıtlı"
        )
    
    # Kullanıcı oluştur
    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role="user",
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcı girişi ve JWT token alma"""
    # Kullanıcıyı bul
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Hesap devre dışı")
    
    # Token oluştur
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )
    
    # Audit log
    ip = request.client.host if request and request.client else None
    ua = request.headers.get("user-agent", "")[:255] if request else None
    await log_action(
        db, user=user, action="login",
        resource="auth", ip_address=ip, user_agent=ua,
    )
    await db.commit()
    
    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Mevcut kullanıcı bilgilerini döner"""
    return current_user

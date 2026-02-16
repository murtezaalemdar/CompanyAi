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
    create_refresh_token,
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
    refresh_token: str | None = None
    token_type: str = "bearer"
    must_change_password: bool = False


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
    # Şifre validasyonu
    if len(user_data.password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Şifre en az {settings.PASSWORD_MIN_LENGTH} karakter olmalıdır"
        )
    if user_data.password.isdigit() or user_data.password.isalpha():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifre hem harf hem rakam içermelidir"
        )
    
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

    ip = request.client.host if request and request.client else None
    ua = request.headers.get("user-agent", "")[:255] if request else None

    # Hesap kilidi kontrolü
    if user and hasattr(user, "locked_until") and user.locked_until:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if user.locked_until > now:
            await log_action(
                db, user=user, action="login_failed",
                resource="auth", ip_address=ip, user_agent=ua,
                details='{"reason": "account_locked"}',
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Hesabınız çok fazla başarısız giriş nedeniyle kilitlendi. Lütfen 15 dakika sonra tekrar deneyin.",
            )

    if not user or not verify_password(form_data.password, user.hashed_password):
        # Başarısız giriş sayacı
        if user and hasattr(user, "failed_login_attempts"):
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            # 5 başarısız giriş → 15 dakika kilitle
            if user.failed_login_attempts >= 5:
                from datetime import datetime, timezone, timedelta
                user.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15)
            await log_action(
                db, user=user, action="login_failed",
                resource="auth", ip_address=ip, user_agent=ua,
                details=f'{{"attempts": {user.failed_login_attempts}}}',
            )
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Hesap devre dışı")

    # Başarılı giriş — sayacı sıfırla
    if hasattr(user, "failed_login_attempts"):
        user.failed_login_attempts = 0
        user.locked_until = None
    
    # Token oluştur — must_change_password bilgisini ekle
    must_change = getattr(user, "must_change_password", False) or False
    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    
    # Audit log
    await log_action(
        db, user=user, action="login",
        resource="auth", ip_address=ip, user_agent=ua,
    )
    await db.commit()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        must_change_password=must_change,
    )


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh token ile yeni access token al"""
    payload = verify_token(body.refresh_token, token_type="refresh")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş refresh token",
        )
    
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
    
    token_data = {"sub": str(user.id), "role": user.role}
    new_access = create_access_token(data=token_data)
    new_refresh = create_refresh_token(data=token_data)
    
    return Token(access_token=new_access, refresh_token=new_refresh)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Mevcut kullanıcı bilgilerini döner"""
    return current_user


# ──────────────────── Şifre Değiştirme ────────────────────

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının kendi şifresini değiştirmesi"""
    # Mevcut şifre doğrulama
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mevcut şifre hatalı",
        )

    # Yeni şifre validasyonu
    if len(body.new_password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Yeni şifre en az {settings.PASSWORD_MIN_LENGTH} karakter olmalıdır",
        )
    if body.new_password.isdigit() or body.new_password.isalpha():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifre hem harf hem rakam içermelidir",
        )
    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yeni şifre eski şifreyle aynı olamaz",
        )

    # Şifreyi güncelle
    current_user.hashed_password = hash_password(body.new_password)
    # must_change_password bayrağını kaldır
    if hasattr(current_user, "must_change_password"):
        current_user.must_change_password = False
    if hasattr(current_user, "password_changed_at"):
        from datetime import datetime, timezone
        current_user.password_changed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()

    # Audit log
    ip = request.client.host if request and request.client else None
    ua = request.headers.get("user-agent", "")[:255] if request else None
    await log_action(
        db, user=current_user, action="password_change",
        resource="auth", ip_address=ip, user_agent=ua,
    )
    await db.commit()

    return {"message": "Şifre başarıyla değiştirildi"}


# ──────────────────── Tema Tercihi ────────────────────

class ThemeRequest(BaseModel):
    theme: str  # "dark" | "light" | "system"


@router.get("/preferences/theme")
async def get_theme(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının tema tercihini döner"""
    from app.db.models import UserPreference
    result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == current_user.id,
            UserPreference.key == "ui_theme",
        )
    )
    pref = result.scalar_one_or_none()
    return {"theme": pref.value if pref else "dark"}


@router.put("/preferences/theme")
async def set_theme(
    body: ThemeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının tema tercihini kaydeder"""
    if body.theme not in ("dark", "light", "system"):
        raise HTTPException(status_code=400, detail="Geçersiz tema değeri")

    from app.db.models import UserPreference
    result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == current_user.id,
            UserPreference.key == "ui_theme",
        )
    )
    pref = result.scalar_one_or_none()

    if pref:
        pref.value = body.theme
    else:
        pref = UserPreference(
            user_id=current_user.id,
            key="ui_theme",
            value=body.theme,
            source="user_settings",
        )
        db.add(pref)

    await db.commit()
    return {"theme": body.theme, "message": "Tema güncellendi"}

"""Konfigürasyon Yönetimi"""

# Versiyon — frontend/src/constants.ts ile eşleşmeli
# Format: MAJOR.MINOR.PATCH (her segment 2 hane, ör. 6.01.00)
# ÖNEMLİ KURAL:
#   MAJOR (baş)  → Major değişiklik (mimari, geriye uyumsuz)
#   MINOR (orta) → Önemli değişiklik (yeni özellik, önemli iyileştirme)
#   PATCH (son)  → Küçük işlem (bugfix, ufak düzeltme)
#   MINOR artınca PATCH=00, MAJOR artınca MINOR=00 ve PATCH=00 olur.
APP_VERSION = "7.17.00"

from pydantic_settings import BaseSettings
from typing import List
import json
import secrets
import warnings


class Settings(BaseSettings):
    """Uygulama ayarları - .env dosyasından veya environment variable'lardan okunur"""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://companyai:password@localhost:5432/companyai"
    
    # Vector Database (pgvector — ayrı chromadb veritabanı)
    VECTOR_DB_URL: str = "postgresql://companyai:companyai@localhost:5433/chromadb"
    
    # JWT Authentication
    SECRET_KEY: str = "change-this-to-a-very-long-random-string-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Admin
    ADMIN_DEFAULT_PASSWORD: str = "admin123"
    
    # LLM (Ollama + Qwen2.5-72B)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:72b"
    VISION_MODEL: str = "minicpm-v"  # v4.4.0: Vision model (OCR + görüntü anlama)
    OMNI_MODEL: str = "minicpm-o"    # v4.5.0: Omni-modal model (görüntü + video + ses)
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Security
    PASSWORD_MIN_LENGTH: int = 8
    RATE_LIMIT_PER_MINUTE: int = 30
    
    # Web Search APIs
    SERPAPI_KEY: str = ""  # serpapi.com — ücretsiz 100 arama/ay
    GOOGLE_API_KEY: str = ""  # Google Custom Search (billing gerektirir)
    GOOGLE_CSE_ID: str = ""
    
    # CORS
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:5173"]'
    
    @property
    def cors_origins_list(self) -> List[str]:
        """CORS origins listesi olarak döner"""
        return json.loads(self.CORS_ORIGINS)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()

# ── Güvenlik Uyarıları (Startup) ──
_DEFAULT_KEY = "change-this-to-a-very-long-random-string-in-production"
if settings.SECRET_KEY == _DEFAULT_KEY:
    warnings.warn(
        "⚠️  SECRET_KEY varsayılan değerde! Production'da mutlaka değiştirin. "
        "Geçici olarak rastgele key üretiliyor.",
        RuntimeWarning,
        stacklevel=1,
    )
    settings.SECRET_KEY = secrets.token_urlsafe(64)

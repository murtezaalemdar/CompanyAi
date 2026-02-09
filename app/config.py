"""Konfigürasyon Yönetimi"""

from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    """Uygulama ayarları - .env dosyasından veya environment variable'lardan okunur"""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://companyai:password@localhost:5432/companyai"
    
    # JWT Authentication
    SECRET_KEY: str = "change-this-to-a-very-long-random-string-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # LLM (Ollama + Llama 3.1)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3.1:8b"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
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

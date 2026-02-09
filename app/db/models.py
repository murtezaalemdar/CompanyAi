"""SQLAlchemy Veritabanı Modelleri"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    """Kullanıcı modeli"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    department = Column(String(100))  # Üretim, Satış, İK, vb.
    role = Column(String(50), default="user")  # admin, manager, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    queries = relationship("Query", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class Query(Base):
    """AI sorgu geçmişi modeli"""
    __tablename__ = "queries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    department = Column(String(100))
    mode = Column(String(100))
    risk_level = Column(String(50))
    confidence = Column(Float)
    processing_time_ms = Column(Integer)  # İşlem süresi (ms)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # İlişkiler
    user = relationship("User", back_populates="queries")


class AuditLog(Base):
    """Denetim kaydı modeli"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100), nullable=False)  # login, logout, query, admin_action
    resource = Column(String(100))  # Etkilenen kaynak
    details = Column(Text)  # JSON formatında detaylar
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # İlişkiler
    user = relationship("User", back_populates="audit_logs")


class SystemSettings(Base):
    """Sistem ayarları modeli"""
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    description = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"))

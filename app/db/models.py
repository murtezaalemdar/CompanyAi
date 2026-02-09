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


class ChatSession(Base):
    """Sohbet oturumu — sayfa yenilense bile korunur, logout ile yeni oturum açılır"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="Yeni Sohbet")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", backref="chat_sessions")
    messages = relationship("ConversationMemory", back_populates="session", order_by="ConversationMemory.created_at")


class ConversationMemory(Base):
    """Kalıcı konuşma hafızası — 'unut' denene kadar saklanır"""
    __tablename__ = "conversation_memory"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    department = Column(String(100))
    intent = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    user = relationship("User", backref="conversation_memories")
    session = relationship("ChatSession", back_populates="messages")


class UserPreference(Base):
    """Kullanıcı tercihleri ve bilgileri — AI'ın hatırlaması gereken şeyler"""
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key = Column(String(100), nullable=False)       # Ör: "name", "favorite_topic", "style"
    value = Column(Text, nullable=False)
    source = Column(String(200))                     # Hangi konuşmadan çıkarıldı
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", backref="preferences")


class CompanyCulture(Base):
    """Şirket kültürü — TÜM konuşmalardan çıkarılan şirket çalışma kalıpları"""
    __tablename__ = "company_culture"
    
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False, index=True)   # report_style, comm_style, tool_preference, workflow
    key = Column(String(200), nullable=False)                     # Ör: "excel_tercih", "rapor_format"
    value = Column(Text, nullable=False)                          # Ör: "Tablo formatında Excel"
    frequency = Column(Integer, default=1)                        # Kaç kez gözlemlendi
    source_user_id = Column(Integer, ForeignKey("users.id"))      # İlk gözlemleyen
    source_text = Column(String(300))                             # Hangi konuşmadan
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

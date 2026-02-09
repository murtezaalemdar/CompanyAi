
import os
import sys

# Windows encoding hack
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Environment force override
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./companyai.db"
os.environ["DEBUG"] = "true"

print("==================================================")
print("🔍 DEBUG MODU BAŞLATILIYOR")
print(f"📂 Veritabanı: {os.environ['DATABASE_URL']}")
print("==================================================")

try:
    import uvicorn
    import fastapi
    import structlog
    import aiosqlite
    import sqlalchemy
    import pydantic
    from passlib.context import CryptContext
    
    print(f"✅ FastAPI: {fastapi.__version__}")
    print(f"✅ SQLAlchemy: {sqlalchemy.__version__}")
    print(f"✅ Pydantic: {pydantic.__version__}")
    print("✅ Tüm kütüphaneler yüklü.")
    
except ImportError as e:
    print(f"❌ EKSİK KÜTÜPHANE: {e}")
    print("Lütfen 'pip install -r requirements.txt' çalıştırın.")
    sys.exit(1)

if __name__ == "__main__":
    try:
        # Main import should be inside try/catch to see import errors
        from app.main import app
        
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8000,
            log_level="debug"
        )
    except Exception as e:
        print("\n\n❌ KRİTİK BAŞLATMA HATASI:")
        import traceback
        traceback.print_exc()
        input("\nKapatmak için Enter'a basın...")

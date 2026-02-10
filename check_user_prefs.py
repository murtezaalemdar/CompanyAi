"""Bozuk kullanıcı tercihlerini düzelt"""
import asyncio
from sqlalchemy import select, update, and_
from app.db.database import async_session_maker
from app.db.models import UserPreference, User

async def fix():
    async with async_session_maker() as db:
        # Bozuk user_name tercihlerini sil (value='ne' gibi saçma değerler)
        prefs = (await db.execute(select(UserPreference))).scalars().all()
        for p in prefs:
            if p.key == "user_name" and p.value.lower() in ("ne", "kim", "nasıl", "var", "yok"):
                print(f"SILINIYOR: user_id={p.user_id} key={p.key} value={p.value}")
                await db.delete(p)
        
        # Kullanıcıların DB'deki full_name'lerini tercih olarak kaydet
        users = (await db.execute(select(User))).scalars().all()
        for u in users:
            if u.full_name and u.full_name.strip():
                # Mevcut user_name tercihi var mı?
                stmt = select(UserPreference).where(
                    and_(UserPreference.user_id == u.id, UserPreference.key == "user_name")
                )
                existing = (await db.execute(stmt)).scalar_one_or_none()
                if not existing:
                    pref = UserPreference(
                        user_id=u.id,
                        key="user_name",
                        value=u.full_name.split()[0],  # İlk isim
                        source="Profil bilgisi",
                    )
                    db.add(pref)
                    print(f"EKLENDI: user_id={u.id} user_name={u.full_name.split()[0]}")
        
        await db.commit()
        
        # Sonucu göster
        prefs = (await db.execute(select(UserPreference))).scalars().all()
        print("\n--- GUNCEL TERCIHLER ---")
        for p in prefs:
            print(f"user_id={p.user_id}: {p.key}={p.value}")

asyncio.run(fix())

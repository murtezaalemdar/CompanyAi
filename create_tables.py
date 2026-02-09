#!/usr/bin/env python3
"""Yeni DB tablolarini olustur"""
import asyncio
from app.db.database import engine, Base
from app.db.models import ConversationMemory, UserPreference, ChatSession, CompanyCulture

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("OK - Tablolar olusturuldu! (ChatSession, CompanyCulture, ConversationMemory, UserPreference)")

asyncio.run(create_tables())

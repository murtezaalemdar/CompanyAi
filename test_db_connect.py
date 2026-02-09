
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text

DATABASE_URL = "postgresql+asyncpg://companyai:your_secure_password@localhost:5432/companyai"

async def main():
    print("Creating engine...")
    engine = create_async_engine(DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        print("Connecting...")
        await conn.execute(text("SELECT 1"))
        print("Connected!")

if __name__ == "__main__":
    asyncio.run(main())

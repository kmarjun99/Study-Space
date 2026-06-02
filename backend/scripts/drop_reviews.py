import asyncio
from app.database import engine
from sqlalchemy import text

async def drop_reviews():
    async with engine.begin() as conn:
        print("Dropping reviews table...")
        await conn.execute(text("DROP TABLE IF EXISTS reviews"))
        print("Dropped reviews table.")

if __name__ == "__main__":
    asyncio.run(drop_reviews())

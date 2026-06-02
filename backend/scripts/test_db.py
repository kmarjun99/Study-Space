import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

DATABASE_URL = "sqlite+aiosqlite:///./study_space.db"

async def test():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Direct query
        result = await session.execute(select("*").select_from("cabins"))
        print("Result:", result.fetchall()[:3])
        
asyncio.run(test())

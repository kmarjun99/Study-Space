from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
import ssl

# Create Async Engine
# Handle SQLite vs Postgres specific arguments
connect_args = {}
engine_kwargs = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # SQLite uses StaticPool — pool sizing kwargs aren't valid here.
elif settings.DATABASE_URL.startswith("postgresql"):
    # For Postgres with asyncpg - SSL verification enabled for security
    # Render's managed PostgreSQL uses proper SSL certificates
    connect_args = {"timeout": 30}
    engine_kwargs = {
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False, # Set to False in production
    future=True,
    connect_args=connect_args,
    **engine_kwargs,
)

# Create Session Factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()

# Dependency to get DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

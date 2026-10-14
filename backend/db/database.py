from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# imported so their tables are registered on SQLModel.metadata before create_all
import app.models  # noqa: F401
import auth.models  # noqa: F401
from config import Config

engine = create_async_engine(Config.DATABASE_URL)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Creates any missing tables. Runs once at startup."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one database session per request."""
    async with SessionLocal() as session:
        yield session

"""
NPIDE - Database layer.

Supports both PostgreSQL and a local SQLite fallback so the project can run
end-to-end even when Postgres is not installed on the machine.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./npide.db")


def _make_async_url(db_url: str) -> str:
    if db_url.startswith("postgresql+asyncpg://") or db_url.startswith("sqlite+aiosqlite:///"):
        return db_url
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return db_url


def _make_sync_url(db_url: str) -> str:
    return db_url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)


ASYNC_DATABASE_URL = _make_async_url(_DB_URL)
SYNC_DATABASE_URL = _make_sync_url(_DB_URL)
IS_SQLITE = SYNC_DATABASE_URL.startswith("sqlite:///")

if IS_SQLITE:
    async_engine: AsyncEngine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=False,
    )
    engine = create_engine(
        SYNC_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
else:
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,
    )
    engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True, echo=False)


if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=MEMORY")
        cursor.execute("PRAGMA synchronous=OFF")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db_dialect() -> str:
    return "sqlite" if IS_SQLITE else "postgresql"


async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def ping_db_async() -> bool:
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[DB-ASYNC] Ping failed: {e}")
        return False


def ping_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[DB-SYNC] Ping failed: {e}")
        return False

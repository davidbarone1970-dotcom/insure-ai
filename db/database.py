"""
INSURE.AI — Async Database Layer
SQLAlchemy 2.x + asyncpg + Supabase Session Mode (Port 5432)
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import logging

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    if url.startswith("postgresql+asyncpg://"):
        pass
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        connect_args = {
            "ssl": "require",
            "statement_cache_size": 100,
            "command_timeout": 30,
            "server_settings": {
                "search_path": "public",
                "application_name": "insure_ai",
            },
        }
        _engine = create_async_engine(
            get_database_url(),
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — use with Depends(db_session)."""
    async with get_session() as session:
        yield session


class Base(DeclarativeBase):
    pass


async def startup() -> None:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT current_database(), version()"))
            db_name, version = result.fetchone()
            logger.info(f"[DB] Connected to '{db_name}' ✓  ({version[:40]}...)")
    except Exception as e:
        logger.error(f"[DB] Connection failed: {e}")
        logger.warning("[DB] Server startet ohne DB — Agents funktionieren, DB-Endpoints nicht")


async def shutdown() -> None:
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("[DB] Connection pool disposed")


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    async def _test():
        await startup()
        async with get_session() as session:
            row = await session.execute(
                text("SELECT table_name FROM information_schema.tables "
                     "WHERE table_schema = 'public' ORDER BY 1 LIMIT 10")
            )
            tables = [r[0] for r in row.fetchall()]
            logger.info(f"[DB] Public tables: {tables or '(none yet)'}")
        await shutdown()

    asyncio.run(_test())
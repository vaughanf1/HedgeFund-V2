import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

# Async engine for FastAPI/async code.
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

# Sync engine for Celery tasks (psycopg2, plain postgresql URL).
# Transforms e.g. "postgresql+asyncpg://..." -> "postgresql+psycopg2://..."
# and "timescaledb://..." -> "postgresql://..."
_sync_url = (
    DATABASE_URL
    .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    .replace("timescaledb+asyncpg://", "postgresql+psycopg2://")
    .replace("timescaledb://", "postgresql+psycopg2://")
)

sync_engine = create_engine(
    _sync_url,
    pool_size=5,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
)

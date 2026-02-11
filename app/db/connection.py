import asyncpg
from typing import Optional

from app.config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    MCQ_DATABASE_NAME, MCQ_DB_HOST, MCQ_DB_PORT, MCQ_DB_USER, MCQ_DB_PASSWORD,
)

_pool: Optional[asyncpg.Pool] = None
_mcq_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD or None,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_mcq_db_pool() -> asyncpg.Pool:
    """Get or create the MCQ database connection pool."""
    global _mcq_pool
    if _mcq_pool is None:
        _mcq_pool = await asyncpg.create_pool(
            host=MCQ_DB_HOST,
            port=MCQ_DB_PORT,
            database=MCQ_DATABASE_NAME,
            user=MCQ_DB_USER,
            password=MCQ_DB_PASSWORD or None,
            min_size=2,
            max_size=10,
        )
    return _mcq_pool


async def close_mcq_db_pool() -> None:
    """Close the MCQ database connection pool."""
    global _mcq_pool
    if _mcq_pool is not None:
        await _mcq_pool.close()
        _mcq_pool = None

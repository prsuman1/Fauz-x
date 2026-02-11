import asyncpg
from datetime import datetime
from typing import Optional


async def ensure_key_usage_table(pool: asyncpg.Pool) -> None:
    """Create the api_key_usage table if it doesn't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_key_usage (
                id          BIGSERIAL PRIMARY KEY,
                key_hint    VARCHAR(10) NOT NULL,
                started_at  TIMESTAMPTZ NOT NULL,
                finished_at TIMESTAMPTZ NOT NULL,
                duration_s  REAL NOT NULL,
                status_code INTEGER,
                model       VARCHAR(100),
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)


async def insert_key_usage(
    pool: asyncpg.Pool,
    key_hint: str,
    started_at: datetime,
    finished_at: datetime,
    duration_s: float,
    status_code: Optional[int] = None,
    model: Optional[str] = None,
) -> None:
    """Insert a key usage record. Failures are silently ignored (fire-and-forget)."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO api_key_usage (key_hint, started_at, finished_at, duration_s, status_code, model)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                key_hint, started_at, finished_at, duration_s, status_code, model,
            )
    except Exception as e:
        print(f"[key_usage] Failed to log usage: {e}")

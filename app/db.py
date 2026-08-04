import asyncpg
import os
import logging
from typing import Optional, List, Dict, Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                operation_id TEXT PRIMARY KEY,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL CHECK(status IN ('CREATED', 'PROCESSING', 'COMPLETED', 'REJECTED')),
                provider_payment_id TEXT,
                created_at TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                operation_id TEXT NOT NULL REFERENCES operations(operation_id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                message TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_events_op ON events(operation_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_status ON operations(status)")
        logger.info("Database initialized")


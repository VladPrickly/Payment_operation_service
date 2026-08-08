import asyncpg
import os
import logging
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

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


async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def _add_event(conn: asyncpg.Connection, op_id: str, event_type: str, from_status: Optional[str], to_status: str,
                     message: str, occurred_at: str):
    await conn.execute(
        """INSERT INTO events (operation_id, type, from_status, to_status, message, occurred_at) 
           VALUES ($1, $2, $3, $4, $5, $6)""",
        op_id, event_type, from_status, to_status, message, occurred_at
    )


async def create_operation(data: dict) -> dict:
    pool = await get_pool()
    now = data.get('occurredAt') or __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()

    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """INSERT INTO operations (operation_id, amount, currency, description, status, created_at) 
                   VALUES ($1, $2, $3, $4, 'CREATED', $5)""",
                data['operationId'], data['amount'], data['currency'], data['description'], now
            )
            await _add_event(conn, data['operationId'], 'CREATED', None, 'CREATED', 'Operation created', now)
            return {**data, 'status': 'CREATED', 'providerPaymentId': None}
        except asyncpg.exceptions.UniqueViolationError:
            raise HTTPException(status_code=409, detail="Operation already exists")


async def get_operation(op_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM operations WHERE operation_id = $1", op_id)
        if not row:
            return None
        return {
            "operationId": row["operation_id"],
            "amount": row["amount"],
            "currency": row["currency"],
            "description": row["description"],
            "status": row["status"],
            "providerPaymentId": row["provider_payment_id"]
        }


async def get_events(op_id: str) -> List[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id as "eventId", type, from_status as "fromStatus", to_status as "toStatus", message, occurred_at as "occurredAt" 
               FROM events WHERE operation_id = $1 ORDER BY id ASC""",
            op_id
        )
        return [dict(row) for row in rows]


async def submit_operation(op_id: str) -> tuple[int, dict]:
    pool = await get_pool()
    now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # FOR UPDATE блокирует строку от конкурентных изменений до конца транзакции
            row = await conn.fetchrow(
                "SELECT status, provider_payment_id FROM operations WHERE operation_id = $1 FOR UPDATE",
                op_id
            )

            if not row:
                raise HTTPException(status_code=404, detail="Operation not found")

            status = row["status"]
            provider_payment_id = row["provider_payment_id"]

            if status == "CREATED":
                await conn.execute(
                    "UPDATE operations SET status = 'PROCESSING' WHERE operation_id = $1",
                    op_id
                )
                await _add_event(conn, op_id, 'SUBMIT', 'CREATED', 'PROCESSING', 'Submit requested', now)
                return 202, {"operationId": op_id, "status": "PROCESSING", "providerPaymentId": provider_payment_id}
            else:
                return 200, {"operationId": op_id, "status": status, "providerPaymentId": provider_payment_id}


async def process_receipt(receipt: dict) -> int:
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT status, provider_payment_id FROM operations WHERE operation_id = $1 FOR UPDATE",
                receipt['operationId']
            )

            if not row:
                raise HTTPException(status_code=404, detail="Operation not found")

            current_status = row["status"]
            db_provider_id = row["provider_payment_id"]

            if db_provider_id is not None and db_provider_id != receipt['providerPaymentId']:
                raise HTTPException(status_code=409, detail="providerPaymentId mismatch")

            if current_status in ("COMPLETED", "REJECTED"):
                return 204

            new_status = receipt['result']
            await conn.execute(
                """UPDATE operations 
                   SET status = $1, provider_payment_id = COALESCE(provider_payment_id, $2) 
                   WHERE operation_id = $3""",
                new_status, receipt['providerPaymentId'], receipt['operationId']
            )
            await _add_event(conn, receipt['operationId'], 'RECEIPT', current_status, new_status, receipt['message'],
                             receipt['occurredAt'])

            return 204


async def get_processing_operations() -> List[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT operation_id, amount, currency FROM operations WHERE status = 'PROCESSING'"
        )
        return [dict(row) for row in rows]


async def save_provider_payment_id(op_id: str, provider_payment_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE operations 
               SET provider_payment_id = $1 
               WHERE operation_id = $2 AND status = 'PROCESSING' AND provider_payment_id IS NULL""",
            provider_payment_id, op_id
        )


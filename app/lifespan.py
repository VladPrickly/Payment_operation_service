import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db, provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup: initializing database...")
    await db.init_db()

    processing_ops = await db.get_processing_operations()
    if processing_ops:
        logger.info("Recovering %d processing operation(s) after restart", len(processing_ops))
        for op in processing_ops:
            logger.info("  → recovering operation %s", op["operation_id"])
            asyncio.create_task(
                provider.send_to_provider(
                    op["operation_id"],
                    op["amount"],
                    op["currency"],
                )
            )
    else:
        logger.info("No processing operations to recover")

    logger.info("Application startup complete")

    yield

    logger.info("Application shutdown: closing database connections...")
    await db.close_db()
    logger.info("Application shutdown complete")


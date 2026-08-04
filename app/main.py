import logging

from fastapi import FastAPI, HTTPException, BackgroundTasks

from app import db, provider
from app.models import OperationCreate, OperationResponse, EventResponse, ReceiptRequest

from app.lifespan import lifespan

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



app = FastAPI(
    title="Payment Candidate Service",
    description="Сервис проведения платёжных операций с гарантией идемпотентности",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}




import logging

from fastapi import FastAPI, HTTPException, BackgroundTasks

from app import db, provider
from app.models import OperationCreate, OperationResponse, EventResponse, ReceiptRequest

from app.lifespan import lifespan

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



app = FastAPI(
    title="Payment Service",
    description="Сервис проведения платёжных операций с гарантией идемпотентности",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}




@app.post("/operations", status_code=201, response_model=OperationResponse)
async def create_operation(op: OperationCreate):
    return await db.create_operation(op.model_dump())


@app.get("/operations/{op_id}", response_model=OperationResponse)
async def get_operation(op_id: str):
    result = await db.get_operation(op_id)
    if not result:
        raise HTTPException(status_code=404, detail="Operation not found")
    return result


@app.get("/operations/{op_id}/events", response_model=list[EventResponse])
async def get_events(op_id: str):
    if not await db.get_operation(op_id):
        raise HTTPException(status_code=404, detail="Operation not found")
    return await db.get_events(op_id)


@app.post("/operations/{op_id}/submit")
async def submit_operation(op_id: str, background_tasks: BackgroundTasks):

    status_code, result = await db.submit_operation(op_id)

    if status_code == 202:
        op_details = await db.get_operation(op_id)
        if op_details:
            background_tasks.add_task(
                provider.send_to_provider,
                op_id,
                op_details["amount"],
                op_details["currency"],
            )

    return result, status_code


@app.post("/receipts", status_code=204)
async def process_receipt(receipt: ReceiptRequest):
    return await db.process_receipt(receipt.model_dump())

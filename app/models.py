from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
import re
from datetime import datetime

class OperationCreate(BaseModel):
    operationId: str = Field(..., min_length=1)
    amount: str
    currency: str
    description: str

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: str) -> str:
        if not re.match(r'^\d+(\.\d{1,2})?$', v):
            raise ValueError('Amount must be a positive decimal with up to 2 decimal places')
        if float(v) <= 0:
            raise ValueError('Amount must be positive')
        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v != 'RUB':
            raise ValueError('Only RUB currency is supported')
        return v

class OperationResponse(BaseModel):
    operationId: str
    amount: str
    currency: str
    description: str
    status: Literal['CREATED', 'PROCESSING', 'COMPLETED', 'REJECTED']
    providerPaymentId: Optional[str] = None

class EventResponse(BaseModel):
    eventId: int
    type: str
    fromStatus: Optional[str]
    toStatus: str
    message: str
    occurredAt: str

class ReceiptRequest(BaseModel):
    providerPaymentId: str
    operationId: str
    result: Literal['COMPLETED', 'REJECTED']
    message: str
    occurredAt: str
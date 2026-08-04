import httpx
import asyncio
import logging
import os

logger = logging.getLogger(__name__)
PROVIDER_URL = os.getenv("PROVIDER_URL")


async def send_to_provider(op_id: str, amount: str, currency: str):
    headers = {
        "Idempotency-Key": op_id,
        "X-Correlation-ID": op_id,
        "Content-Type": "application/json"
    }
    payload = {
        "operationId": op_id,
        "amount": amount,
        "currency": currency
    }

    max_retries = 5
    backoff = 1.0

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{PROVIDER_URL}/payments", json=payload, headers=headers)

                if response.status_code == 202:
                    data = response.json()
                    provider_payment_id = data.get("providerPaymentId")
                    if provider_payment_id:
                        from app.db import save_provider_payment_id
                        await save_provider_payment_id(op_id, provider_payment_id)
                    logger.info(f"Provider accepted payment {op_id}")
                    return True

                elif response.status_code == 503:
                    logger.warning(f"Provider 503 for {op_id}, attempt {attempt + 1}")
                else:
                    logger.error(f"Provider unexpected status {response.status_code} for {op_id}")

                    return False

        except httpx.RequestError as e:
            logger.warning(f"Network error for {op_id}, attempt {attempt + 1}: {e}")

        await asyncio.sleep(backoff)
        backoff *= 2

    logger.error(f"Failed to send to provider after {max_retries} attempts for {op_id}")
    return False
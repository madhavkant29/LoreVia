from fastapi import APIRouter, Header, HTTPException, Request

from app.services.paddle_service import paddle_webhooks_configured, verify_webhook_signature
from app.services.paddle_webhook_service import process_paddle_webhook
from app.utils.billing_utils import event_id_from_paddle_payload

router = APIRouter()


@router.post("/paddle")
async def paddle_webhook(
    request: Request, paddle_signature: str | None = Header(default=None, alias="Paddle-Signature")
):
    if not paddle_webhooks_configured():
        raise HTTPException(503, "Paddle webhooks are not configured")

    payload = await request.body()
    if not verify_webhook_signature(payload, paddle_signature):
        raise HTTPException(400, "Invalid request.")

    try:
        event = await request.json()
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(400, "Invalid request.")
    event_id = event_id_from_paddle_payload(event)
    if not event_id:
        raise HTTPException(400, "Missing Paddle event ID")
    return await process_paddle_webhook(event)

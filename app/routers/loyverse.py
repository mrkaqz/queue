import hashlib
import hmac
import json

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app import database as db
from app.routers.queue import _do_loyverse_advance

router = APIRouter(tags=["loyverse"])


@router.post("/api/loyverse/webhook")
async def loyverse_webhook(request: Request):
    """Receive Loyverse POS webhook events and advance the queue on sale completion."""
    # Always return 200 quickly — Loyverse retries on non-200 responses
    body = await request.body()

    # Check feature enabled
    enabled = await db.get_setting("loyverse_auto_advance")
    if enabled != "true":
        return Response(status_code=200)

    # Verify HMAC-SHA256 signature if a secret is configured
    secret = (await db.get_setting("loyverse_webhook_secret") or "").strip()
    if secret:
        sig_header = request.headers.get("X-Loyverse-Webhook-Signature", "")
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig_header):
            return Response(status_code=200)   # silently ignore invalid signature

    # Parse JSON payload
    try:
        payload = json.loads(body)
    except Exception:
        return Response(status_code=200)

    # Detect a receipt-creation event
    # Loyverse "receipt" = completed sale record (not printed paper).
    # We subscribe only to the sale-completed event in the Loyverse dashboard,
    # so every validated payload we receive IS a completed sale.
    # Guard against UPDATED events by requiring "CREATED" in the type string.
    event_type = payload.get("type", "").upper()
    is_receipt_event = (
        ("RECEIPT" in event_type and "CREATED" in event_type)
        or (not event_type and ("receipt" in payload or "receipts" in payload))
    )

    if is_receipt_event:
        behaviour = (await db.get_setting("loyverse_queue_behaviour") or "smart")
        await _do_loyverse_advance(smart=(behaviour == "smart"))

    return Response(status_code=200)

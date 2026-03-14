import asyncio
import hashlib
import hmac
import json
import re

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app import database as db

router = APIRouter(prefix="/api/messenger", tags=["messenger"])

_NUMBER_RE = re.compile(r"^\d{1,4}$")
_GRAPH_URL  = "https://graph.facebook.com/v20.0/me/messages"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verify_signature(app_secret: str, body: bytes, header: str) -> bool:
    """Verify X-Hub-Signature-256 using HMAC-SHA256."""
    expected = "sha256=" + hmac.new(
        app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)


async def _send_message(token: str, psid: str, text: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                _GRAPH_URL,
                params={"access_token": token},
                json={
                    "recipient":      {"id": psid},
                    "messaging_type": "RESPONSE",
                    "message":        {"text": text},
                },
            )
    except Exception as e:
        print(f"[Messenger] Send failed to {psid}: {e}")


async def _handle_message(psid: str, text: str) -> None:
    """Bot conversation logic."""
    token = await db.get_setting("facebook_page_access_token")
    if not token:
        return

    t = text.strip().lower()

    # Unsubscribe command
    if t in ("cancel", "ยกเลิก", "unsub", "unsubscribe"):
        await db.delete_messenger_sub(psid)
        await _send_message(
            token, psid,
            "✅ ยกเลิกการแจ้งเตือนแล้ว · Unsubscribed. No more notifications.",
        )
        return

    # Queue number
    if _NUMBER_RE.match(text.strip()):
        queue_num = int(text.strip())
        padding   = int(await db.get_setting("queue_padding", "3"))
        display   = str(queue_num).zfill(padding)
        await db.save_messenger_sub(psid, queue_num)
        await _send_message(
            token, psid,
            f"✅ สมัครรับแจ้งเตือนสำหรับคิว {display} แล้ว\n"
            f"Subscribed for queue {display}. You'll be notified when called.\n\n"
            f"พิมพ์ 'cancel' เพื่อยกเลิก · Type 'cancel' to unsubscribe.",
        )
        return

    # Greeting / default
    await _send_message(
        token, psid,
        "สวัสดี! · Hello!\n\n"
        "ส่งหมายเลขคิวของคุณ (เช่น 005) เพื่อรับแจ้งเตือนเมื่อถูกเรียก\n"
        "Send your queue number (e.g. 005) to get notified when called.\n\n"
        "พิมพ์ 'cancel' เพื่อยกเลิก · Type 'cancel' to unsubscribe.",
    )


# ── Public notify function (called from queue router) ─────────────────────────

async def notify_messenger_subscribers(queue_number: int, display: str) -> None:
    """Send Messenger notification to all subscribers for the given queue number."""
    token = await db.get_setting("facebook_page_access_token")
    if not token:
        return

    psids = await db.get_messenger_subs(queue_number)
    if not psids:
        return

    msg = (
        f"🔔 หมายเลขคิว {display} ถูกเรียกแล้ว กรุณาเข้ารับบริการ\n"
        f"Queue {display} is now being served. Please proceed to the counter."
    )

    async with httpx.AsyncClient(timeout=10) as client:
        for psid in psids:
            try:
                await client.post(
                    _GRAPH_URL,
                    params={"access_token": token},
                    json={
                        "recipient":      {"id": psid},
                        "messaging_type": "UPDATE",
                        "message":        {"text": msg},
                    },
                )
            except Exception as e:
                print(f"[Messenger] Notify failed for {psid}: {e}")

    # Clean up: subscriptions are one-shot (re-subscribe each visit)
    for psid in psids:
        await db.delete_messenger_sub(psid)


# ── Webhook endpoints ─────────────────────────────────────────────────────────

@router.get("/webhook")
async def verify_webhook(
    hub_mode:      str = Query(alias="hub.mode",         default=""),
    hub_token:     str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge",    default=""),
):
    """Facebook webhook verification challenge."""
    verify_token = await db.get_setting("facebook_webhook_verify_token")
    if hub_mode == "subscribe" and verify_token and hub_token == verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("/webhook")
async def receive_webhook(request: Request):
    """Receive Messenger events from Facebook."""
    raw_body   = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    app_secret = await db.get_setting("facebook_app_secret")

    # Verify HMAC signature if app secret is configured
    if app_secret and sig_header:
        if not _verify_signature(app_secret, raw_body, sig_header):
            raise HTTPException(status_code=403, detail="Bad signature")

    try:
        data = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if data.get("object") != "page":
        return {"status": "ok"}

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            # Only handle standard text messages (ignore echoes, read receipts, etc.)
            if "message" not in event:
                continue
            if event["message"].get("is_echo"):
                continue
            psid = event["sender"]["id"]
            text = event["message"].get("text", "").strip()
            if text:
                asyncio.create_task(_handle_message(psid, text))

    return {"status": "ok"}

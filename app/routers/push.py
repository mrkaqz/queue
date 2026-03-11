import json
from fastapi import APIRouter, HTTPException
from app import database as db
from app.models import PushSubscription
import aiosqlite

router = APIRouter(prefix="/api/push", tags=["push"])


@router.get("/vapid-key")
async def get_vapid_key():
    public_key = await db.get_setting("vapid_public_key")
    return {"public_key": public_key}


@router.post("/subscribe")
async def subscribe(sub: PushSubscription):
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO push_subscriptions (queue_number, endpoint, p256dh, auth)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET
                queue_number = excluded.queue_number,
                p256dh = excluded.p256dh,
                auth = excluded.auth
            """,
            (sub.queue_number, sub.endpoint, sub.p256dh, sub.auth),
        )
        await conn.commit()
    return {"message": "Subscribed"}


@router.post("/unsubscribe")
async def unsubscribe(data: dict):
    endpoint = data.get("endpoint")
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint required")
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute(
            "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
        )
        await conn.commit()
    return {"message": "Unsubscribed"}


async def notify_subscribers(queue_number: int, message: str):
    """Send push notification to all subscribers for a given queue number."""
    vapid_email = await db.get_setting("vapid_email")
    vapid_private_key = await db.get_setting("vapid_private_key")
    vapid_public_key = await db.get_setting("vapid_public_key")

    if not vapid_private_key or not vapid_email:
        return  # Push not configured

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return

    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM push_subscriptions WHERE queue_number = ?", (queue_number,)
        ) as cur:
            subs = await cur.fetchall()

    for sub in subs:
        try:
            subscription_info = {
                "endpoint": sub["endpoint"],
                "keys": {
                    "p256dh": sub["p256dh"],
                    "auth": sub["auth"],
                },
            }
            webpush(
                subscription_info=subscription_info,
                data=json.dumps({"title": "Your number is ready!", "body": message}),
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": f"mailto:{vapid_email}"},
            )
        except Exception as e:
            print(f"[Push] Failed to notify {sub['endpoint']}: {e}")

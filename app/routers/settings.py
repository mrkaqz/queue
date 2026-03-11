from fastapi import APIRouter
from app import database as db
from app.websocket import manager

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings():
    raw = await db.get_all_settings()
    # Don't expose private VAPID key to frontend
    safe = {k: v for k, v in raw.items() if k != "vapid_private_key"}
    return safe


@router.put("")
async def update_settings(data: dict):
    # Don't allow overwriting generated VAPID keys via this endpoint unless explicitly set
    await db.set_settings(data)
    # Broadcast so all pages can update shop name etc.
    settings = await db.get_all_settings()
    await manager.broadcast({
        "event": "settings_updated",
        "shop_name": settings.get("shop_name", "My Queue"),
        "announcement_message": settings.get("announcement_message", ""),
    })
    return {"message": "Settings updated"}

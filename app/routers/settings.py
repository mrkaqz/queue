import asyncio

from fastapi import APIRouter, Depends, UploadFile, File
from app import database as db
from app.websocket import manager
from app.routers.auth import require_auth

_VOICE_KEYS = {"announcement_language", "thai_voice", "english_voice"}


async def _rewarm():
    from app import tts as _tts
    lang = await db.get_setting("announcement_language", "th")
    v_th  = await db.get_setting("thai_voice", "th-TH-PremwadeeNeural")
    v_en  = await db.get_setting("english_voice", "en-US-JennyNeural")
    print(f"[TTS] Re-warming audio after settings change (lang={lang})")
    await _tts.warmup(list(range(1, 101)), lang, v_th, v_en)
    print("[TTS] Re-warmup complete")

router = APIRouter(prefix="/api/settings", tags=["settings"])

_ALLOWED_LOGO_TYPES = {
    "image/jpeg": ".jpg",
    "image/png":  ".png",
    "image/gif":  ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


@router.get("", dependencies=[Depends(require_auth)])
async def get_settings():
    raw = await db.get_all_settings()
    safe = {k: v for k, v in raw.items()
            if k not in ("vapid_private_key", "admin_pin",
                         "facebook_page_access_token", "facebook_app_secret")}
    return safe


@router.put("", dependencies=[Depends(require_auth)])
async def update_settings(data: dict):
    await db.set_settings(data)
    settings = await db.get_all_settings()
    await manager.broadcast({
        "event": "settings_updated",
        "shop_name": settings.get("shop_name", "My Queue"),
        "announcement_message": settings.get("announcement_message", ""),
        "shop_logo": settings.get("shop_logo", ""),
        "admin_sound": settings.get("admin_sound", "false"),
    })
    if _VOICE_KEYS & set(data.keys()):
        asyncio.create_task(_rewarm())
    return {"message": "Settings updated"}


@router.post("/logo", dependencies=[Depends(require_auth)])
async def upload_logo(file: UploadFile = File(...)):
    if file.content_type not in _ALLOWED_LOGO_TYPES:
        return {"error": "Invalid file type. Use JPEG, PNG, GIF, WebP, or SVG."}

    logo_dir = db.DATA_DIR / "logo"
    logo_dir.mkdir(parents=True, exist_ok=True)

    # Remove any previous logo file
    for old in logo_dir.glob("shop_logo.*"):
        old.unlink()

    ext = _ALLOWED_LOGO_TYPES[file.content_type]
    filepath = logo_dir / f"shop_logo{ext}"
    filepath.write_bytes(await file.read())

    logo_url = f"/logo/shop_logo{ext}"
    await db.set_setting("shop_logo", logo_url)

    settings = await db.get_all_settings()
    await manager.broadcast({
        "event": "settings_updated",
        "shop_name": settings.get("shop_name", "My Queue"),
        "announcement_message": settings.get("announcement_message", ""),
        "shop_logo": logo_url,
        "admin_sound": settings.get("admin_sound", "tv"),
    })
    return {"logo_url": logo_url}


@router.delete("/logo", dependencies=[Depends(require_auth)])
async def remove_logo():
    logo_dir = db.DATA_DIR / "logo"
    for old in logo_dir.glob("shop_logo.*"):
        old.unlink()

    await db.set_setting("shop_logo", "")

    settings = await db.get_all_settings()
    await manager.broadcast({
        "event": "settings_updated",
        "shop_name": settings.get("shop_name", "My Queue"),
        "announcement_message": settings.get("announcement_message", ""),
        "shop_logo": "",
        "admin_sound": settings.get("admin_sound", "tv"),
    })
    return {"message": "Logo removed"}

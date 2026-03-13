import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import database as db
from app.websocket import manager
from app.routers import queue as queue_router
from app.routers import settings as settings_router
from app.routers import push as push_router
from app.routers import auth as auth_router
from app.routers import stats as stats_router

STATIC_DIR = Path(__file__).parent / "static"
AUDIO_DIR = db.DATA_DIR / "audio"
LOGO_DIR  = db.DATA_DIR / "logo"


# ── VAPID key auto-generation ────────────────────────────────────────────────

def _generate_vapid_keys() -> tuple[str, str]:
    """Generate VAPID key pair. Returns (public_key_b64url, private_key_pem)."""
    import base64
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption
    )
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_bytes = private_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_key_b64 = base64.urlsafe_b64encode(public_bytes).rstrip(b'=').decode()
    private_key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()).decode()
    return public_key_b64, private_key_pem


# ── Daily reset scheduler ────────────────────────────────────────────────────

async def _daily_reset_loop():
    last_reset_date = None
    while True:
        await asyncio.sleep(30)
        try:
            reset_time = await db.get_setting("daily_reset_time", "00:00")
            from datetime import datetime, time
            now = datetime.now()
            hour, minute = (int(x) for x in reset_time.split(":"))
            target = time(hour, minute)
            today = now.date()
            if (
                now.hour == target.hour
                and now.minute == target.minute
                and last_reset_date != today
            ):
                await db.reset_queue()
                await manager.broadcast({"event": "queue_reset", "reason": "daily_reset"})
                last_reset_date = today
        except Exception as e:
            print(f"[Scheduler] Error: {e}")


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import tts as _tts

    await db.init_db()

    async def _run_warmup():
        lang = await db.get_setting("announcement_language", "th")
        v_th  = await db.get_setting("thai_voice", "th-TH-PremwadeeNeural")
        v_en  = await db.get_setting("english_voice", "en-US-JennyNeural")
        print(f"[TTS] Warming up audio for numbers 1-100 (lang={lang})")
        await _tts.warmup(list(range(1, 101)), lang, v_th, v_en)
        print("[TTS] Warmup complete")

    asyncio.create_task(_run_warmup())

    # Generate VAPID keys if not present
    pub = await db.get_setting("vapid_public_key")
    if not pub:
        try:
            public_key, private_key = _generate_vapid_keys()
            await db.set_setting("vapid_public_key", public_key)
            await db.set_setting("vapid_private_key", private_key)
            print("[VAPID] Generated new key pair")
        except Exception as e:
            print(f"[VAPID] Could not generate keys: {e}")

    task = asyncio.create_task(_daily_reset_loop())
    yield
    task.cancel()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Queue", lifespan=lifespan)

# Static files (CSS, JS, icons, audio)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
LOGO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")
app.mount("/logo",  StaticFiles(directory=str(LOGO_DIR)),  name="logo")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# API routers
app.include_router(auth_router.router)
app.include_router(queue_router.router)
app.include_router(settings_router.router)
app.include_router(push_router.router)
app.include_router(stats_router.router)


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "tv" / "index.html")


@app.get("/tv")
async def tv_page():
    return FileResponse(STATIC_DIR / "tv" / "index.html")


@app.get("/admin")
async def admin_page():
    return FileResponse(STATIC_DIR / "admin" / "index.html")


@app.get("/settings")
async def settings_page():
    return FileResponse(STATIC_DIR / "settings" / "index.html")


@app.get("/status")
async def status_page():
    return FileResponse(STATIC_DIR / "status" / "index.html")


@app.get("/stats")
async def stats_page():
    return FileResponse(STATIC_DIR / "stats" / "index.html")


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # Send current state on connect
    try:
        status = await db.get_queue_status()
        settings = await db.get_all_settings()
        await ws.send_text(json.dumps({
            "event": "init",
            "status": status,
            "shop_name": settings.get("shop_name", "My Queue"),
            "announcement_message": settings.get("announcement_message", ""),
            "shop_logo": settings.get("shop_logo", ""),
        }))
        while True:
            await ws.receive_text()  # keep alive; clients don't send messages
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)

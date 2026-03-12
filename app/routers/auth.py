import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Header, HTTPException

from app import database as db

router = APIRouter(prefix="/api/auth", tags=["auth"])

_TOKEN_TTL = timedelta(hours=8)
_sessions: dict[str, datetime] = {}  # token -> expiry


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


def _new_token() -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = datetime.now() + _TOKEN_TTL
    return token


def _validate_token(token: str) -> bool:
    expiry = _sessions.get(token)
    if not expiry:
        return False
    if datetime.now() > expiry:
        _sessions.pop(token, None)
        return False
    return True


async def require_auth(authorization: str = Header(default="")):
    """FastAPI dependency — raises 401 if the Bearer token is missing or invalid."""
    token = authorization.removeprefix("Bearer ").strip()
    if not _validate_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def auth_status():
    """Return whether a PIN has been configured (public — no token required)."""
    pin_hash = await db.get_setting("admin_pin", "")
    return {"pin_set": bool(pin_hash)}


@router.post("/set-pin")
async def set_pin(data: dict):
    """Set the PIN for the first time (public — no token required)."""
    pin = str(data.get("pin", "")).strip()
    if len(pin) != 4 or not pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
    existing = await db.get_setting("admin_pin", "")
    if existing:
        raise HTTPException(status_code=400, detail="PIN already set — use change-pin to update it")
    await db.set_setting("admin_pin", _hash(pin))
    token = _new_token()
    return {"ok": True, "token": token}


@router.post("/verify-pin")
async def verify_pin(data: dict):
    """Verify PIN and return a session token on success (public — no token required)."""
    pin = str(data.get("pin", "")).strip()
    stored = await db.get_setting("admin_pin", "")
    if not stored or _hash(pin) != stored:
        return {"ok": False}
    token = _new_token()
    return {"ok": True, "token": token}


@router.post("/change-pin")
async def change_pin(data: dict, authorization: str = Header(default="")):
    """Change the PIN — requires a valid session token."""
    token = authorization.removeprefix("Bearer ").strip()
    if not _validate_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    current_pin = str(data.get("current_pin", "")).strip()
    new_pin     = str(data.get("new_pin", "")).strip()

    if len(new_pin) != 4 or not new_pin.isdigit():
        raise HTTPException(status_code=400, detail="New PIN must be exactly 4 digits")

    stored = await db.get_setting("admin_pin", "")
    if not stored or _hash(current_pin) != stored:
        return {"ok": False, "detail": "Incorrect current PIN"}

    await db.set_setting("admin_pin", _hash(new_pin))
    return {"ok": True}

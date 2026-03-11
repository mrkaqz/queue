import os
import aiosqlite
from pathlib import Path

DATA_DIR = Path(os.environ.get("QUEUE_DATA_DIR", Path(__file__).parent.parent / "data"))
DB_PATH = DATA_DIR / "queue.db"

SETTING_DEFAULTS = {
    "shop_name": "My Queue",
    "shop_logo": "",
    "base_url": "",
    "queue_padding": "3",
    "daily_reset_time": "00:00",
    "announcement_sound": "chime",
    "announcement_message": "",
    "announcement_language": "th",
    "thai_voice": "th-TH-PremwadeeNeural",
    "english_voice": "en-US-JennyNeural",
    "vapid_email": "",
    "vapid_public_key": "",
    "vapid_private_key": "",
}


async def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                number      INTEGER NOT NULL,
                status      TEXT NOT NULL DEFAULT 'waiting',
                created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                called_at   TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                queue_number INTEGER,
                endpoint     TEXT NOT NULL UNIQUE,
                p256dh       TEXT NOT NULL,
                auth         TEXT NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        for key, value in SETTING_DEFAULTS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        await db.commit()


async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else default


async def get_all_settings() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM settings") as cur:
            rows = await cur.fetchall()
            return {r[0]: r[1] for r in rows}


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await db.commit()


async def set_settings(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        for key, value in data.items():
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
        await db.commit()


# ── Queue helpers ────────────────────────────────────────────────────────────

def _fmt(number: int, padding: int) -> str:
    return str(number).zfill(padding)


async def get_queue_status() -> dict:
    padding = int(await get_setting("queue_padding", "3"))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT number FROM queue WHERE status = 'serving' ORDER BY id DESC LIMIT 1"
        ) as cur:
            serving = await cur.fetchone()

        async with db.execute(
            "SELECT number FROM queue WHERE status = 'waiting' ORDER BY number ASC LIMIT 1"
        ) as cur:
            nxt = await cur.fetchone()

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM queue WHERE status = 'waiting'"
        ) as cur:
            row = await cur.fetchone()
            waiting = row["cnt"] if row else 0

    return {
        "current": _fmt(serving["number"], padding) if serving else None,
        "current_number": serving["number"] if serving else None,
        "next": _fmt(nxt["number"], padding) if nxt else None,
        "waiting": waiting,
    }


async def get_queue_list() -> list:
    padding = int(await get_setting("queue_padding", "3"))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM queue ORDER BY number ASC"
        ) as cur:
            rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "number": r["number"],
            "number_display": _fmt(r["number"], padding),
            "status": r["status"],
            "created_at": r["created_at"],
            "called_at": r["called_at"],
        }
        for r in rows
    ]


async def add_queue_entry() -> dict:
    padding = int(await get_setting("queue_padding", "3"))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(MAX(number), 0) as mx FROM queue"
        ) as cur:
            row = await cur.fetchone()
            next_num = (row[0] if row else 0) + 1
        await db.execute(
            "INSERT INTO queue (number, status) VALUES (?, 'waiting')",
            (next_num,),
        )
        await db.commit()
    return {"number": next_num, "number_display": _fmt(next_num, padding)}


async def call_next() -> dict | None:
    """Mark current serving as served, call next waiting. Returns called entry or None."""
    padding = int(await get_setting("queue_padding", "3"))
    async with aiosqlite.connect(DB_PATH) as db:
        # Mark any currently serving as served
        await db.execute(
            "UPDATE queue SET status = 'served' WHERE status = 'serving'"
        )
        # Get next waiting
        async with db.execute(
            "SELECT id, number FROM queue WHERE status = 'waiting' ORDER BY number ASC LIMIT 1"
        ) as cur:
            nxt = await cur.fetchone()
        if not nxt:
            await db.commit()
            return None
        # Set to serving
        await db.execute(
            "UPDATE queue SET status = 'serving', called_at = datetime('now','localtime') WHERE id = ?",
            (nxt[0],),
        )
        await db.commit()
    return {"number": nxt[1], "number_display": _fmt(nxt[1], padding)}


async def recall_current() -> dict | None:
    padding = int(await get_setting("queue_padding", "3"))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT number FROM queue WHERE status = 'serving' LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {"number": row[0], "number_display": _fmt(row[0], padding)}


async def skip_current() -> dict | None:
    """Skip current serving number, call next waiting."""
    padding = int(await get_setting("queue_padding", "3"))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, number FROM queue WHERE status = 'serving' LIMIT 1"
        ) as cur:
            current = await cur.fetchone()
        if not current:
            return None
        await db.execute(
            "UPDATE queue SET status = 'skipped' WHERE id = ?", (current[0],)
        )
        async with db.execute(
            "SELECT id, number FROM queue WHERE status = 'waiting' ORDER BY number ASC LIMIT 1"
        ) as cur:
            nxt = await cur.fetchone()
        if nxt:
            await db.execute(
                "UPDATE queue SET status = 'serving', called_at = datetime('now','localtime') WHERE id = ?",
                (nxt[0],),
            )
        await db.commit()
    skipped = _fmt(current[1], padding)
    called = _fmt(nxt[1], padding) if nxt else None
    return {"skipped": skipped, "called": called, "number": nxt[1] if nxt else None,
            "number_display": called}


async def hold_current() -> dict | None:
    padding = int(await get_setting("queue_padding", "3"))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, number FROM queue WHERE status = 'serving' LIMIT 1"
        ) as cur:
            current = await cur.fetchone()
        if not current:
            return None
        await db.execute(
            "UPDATE queue SET status = 'held' WHERE id = ?", (current[0],)
        )
        await db.commit()
    return {"number": current[1], "number_display": _fmt(current[1], padding)}


async def remove_last_waiting() -> dict | None:
    """Remove the highest-numbered waiting entry. Returns the removed entry or None."""
    padding = int(await get_setting("queue_padding", "3"))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, number FROM queue WHERE status = 'waiting' ORDER BY number DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        await db.execute("DELETE FROM queue WHERE id = ?", (row[0],))
        await db.commit()
    return {"number": row[1], "number_display": _fmt(row[1], padding)}


async def reset_queue():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM queue")
        await db.commit()

import os
import aiosqlite
from pathlib import Path
from app.time_sync import time_sync

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
    "admin_sound": "tv",
    "admin_pin": "",          # SHA-256 hash of the admin PIN; empty = not configured
    "timezone": "0",          # UTC offset as number e.g. "0"=UTC, "7"=Bangkok (UTC+7), "-5"=New York (EST)
    "queue_counter": "0",     # current queue number counter; reset to 0 on each queue reset
    "queue_session": "1",     # increments on every reset; used to scope the queue list to the current session
    "vapid_email": "",
    "vapid_public_key": "",
    "vapid_private_key": "",
    "facebook_page_access_token": "",
    "facebook_app_secret":        "",
    "facebook_webhook_verify_token": "",
    "facebook_page_username":     "",
    "google_analytics_id":        "",
    "loyverse_webhook_secret":    "",
    "loyverse_auto_advance":      "false",
    "loyverse_queue_behaviour":   "smart",   # "smart" | "call_next_only"
    "loyverse_advance_paused":    "false",   # temporary admin-page pause flag
    "xprinter_ip":                "",
    "xprinter_port":              "9100",
    "xprinter_enabled":           "false",   # auto-print on Add Queue
    "xprinter_shop_name":         "",        # ASCII-only name for ticket header; falls back to shop_name if empty
}


async def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                number      INTEGER NOT NULL,
                status      TEXT NOT NULL DEFAULT 'waiting',
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                called_at   TEXT,
                session     INTEGER NOT NULL DEFAULT 1
            )
        """)
        # Add session column to existing installations that predate this field
        async with db.execute("PRAGMA table_info(queue)") as cur:
            cols = [r[1] for r in await cur.fetchall()]
        if "session" not in cols:
            await db.execute("ALTER TABLE queue ADD COLUMN session INTEGER NOT NULL DEFAULT 1")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messenger_subscriptions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                psid          TEXT NOT NULL UNIQUE,
                queue_number  INTEGER,
                subscribed_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                queue_number INTEGER,
                endpoint     TEXT NOT NULL UNIQUE,
                p256dh       TEXT NOT NULL,
                auth         TEXT NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        for key, value in SETTING_DEFAULTS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        # Migrate legacy boolean admin_sound value
        await db.execute(
            "UPDATE settings SET value = 'tv' WHERE key = 'admin_sound' AND value = 'false'"
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
        "next_number": nxt["number"] if nxt else None,
        "waiting": waiting,
    }


async def get_queue_list() -> list:
    padding = int(await get_setting("queue_padding", "3"))
    session = int(await get_setting("queue_session", "1") or "1")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM queue WHERE session = ? ORDER BY number ASC", (session,)
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
            "SELECT key, value FROM settings WHERE key IN ('queue_counter', 'queue_session')"
        ) as cur:
            s = {r[0]: r[1] for r in await cur.fetchall()}
        next_num = int(s.get("queue_counter", "0")) + 1
        session  = int(s.get("queue_session",  "1"))
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('queue_counter', ?)",
            (str(next_num),),
        )
        await db.execute(
            "INSERT INTO queue (number, status, created_at, session) VALUES (?, 'waiting', ?, ?)",
            (next_num, time_sync.utc_iso(), session),
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
            "UPDATE queue SET status = 'serving', called_at = ? WHERE id = ?",
            (time_sync.utc_iso(), nxt[0]),
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
                "UPDATE queue SET status = 'serving', called_at = ? WHERE id = ?",
                (time_sync.utc_iso(), nxt[0]),
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


async def resume_held(number: int) -> dict | None:
    """Bring a specific held entry back to serving. Marks any current serving as served first."""
    padding = int(await get_setting("queue_padding", "3"))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE queue SET status = 'served' WHERE status = 'serving'")
        async with db.execute(
            "SELECT id, number FROM queue WHERE status = 'held' AND number = ? LIMIT 1",
            (number,),
        ) as cur:
            held = await cur.fetchone()
        if not held:
            await db.commit()
            return None
        await db.execute(
            "UPDATE queue SET status = 'serving', called_at = ? WHERE id = ?",
            (time_sync.utc_iso(), held[0]),
        )
        await db.commit()
    return {"number": held[1], "number_display": _fmt(held[1], padding)}


async def reset_queue():
    async with aiosqlite.connect(DB_PATH) as db:
        # Remove all active entries including held (held patients can't return after a reset)
        await db.execute("DELETE FROM queue WHERE status IN ('waiting', 'serving', 'held')")
        # Clear stale Messenger subscriptions — they're only valid within the current day
        await db.execute("DELETE FROM messenger_subscriptions")
        # Reset counter so next queue starts from 1
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('queue_counter', '0')"
        )
        # Increment session so the queue list only shows post-reset entries
        async with db.execute(
            "SELECT value FROM settings WHERE key = 'queue_session'"
        ) as cur:
            row = await cur.fetchone()
        new_session = int(row[0]) + 1 if row else 2
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('queue_session', ?)",
            (str(new_session),),
        )
        await db.commit()


# ── Statistics helpers ────────────────────────────────────────────────────────

def _make_stats_result(rows, labels_all: list, peak_rows) -> dict:
    """Merge sparse DB rows into a zero-filled result dict."""
    row_map = {r[0]: r for r in rows}
    peak_map = {r[0]: r[1] for r in peak_rows}

    labels, total, served, skipped, held, avg_wait = [], [], [], [], [], []
    for lbl in labels_all:
        r = row_map.get(lbl)
        labels.append(lbl)
        total.append(int(r[1]) if r else 0)
        served.append(int(r[2]) if r else 0)
        skipped.append(int(r[3]) if r else 0)
        held.append(int(r[4]) if r else 0)
        avg_wait.append(round(float(r[5]), 1) if r and r[5] is not None else None)

    # Peak hours (hour-of-day distribution, always 24 buckets)
    hours_all = [f"{h:02d}" for h in range(24)]
    peak_total = [int(peak_map.get(h, 0)) for h in hours_all]
    busiest_idx = peak_total.index(max(peak_total)) if any(peak_total) else 0
    busiest_hour = hours_all[busiest_idx]
    busiest_count = peak_total[busiest_idx]

    # KPI aggregates
    t = sum(total)
    s = sum(served)
    sk = sum(skipped) + sum(held)
    wait_vals = [v for v in avg_wait if v is not None]
    avg_w = round(sum(wait_vals) / len(wait_vals), 1) if wait_vals else None

    return {
        "labels": labels,
        "total": total,
        "served": served,
        "skipped": skipped,
        "held": held,
        "avg_wait_minutes": avg_wait,
        "peak_hours": {"labels": hours_all, "total": peak_total},
        "kpi": {
            "total_issued": t,
            "total_served": s,
            "total_skipped_held": sk,
            "avg_wait_minutes": avg_w,
            "busiest_hour": busiest_hour,
            "busiest_hour_count": busiest_count,
        },
    }


def _tz_expr(col: str, offset: float) -> str:
    """Wrap a SQLite column with a UTC offset modifier so strftime returns local time."""
    if offset == 0:
        return col
    sign = "+" if offset >= 0 else "-"
    h = abs(int(offset))
    m = int(round((abs(offset) - h) * 60))
    mod = f"{sign}{h} hours" if m == 0 else f"{sign}{h} hours, {sign}{m} minutes"
    return f"datetime({col}, '{mod}')"


_CHART_SQL = """
    SELECT {lbl_expr} AS lbl,
           COUNT(*) AS total,
           SUM(CASE WHEN status='served'  THEN 1 ELSE 0 END) AS served,
           SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END) AS skipped,
           SUM(CASE WHEN status='held'    THEN 1 ELSE 0 END) AS held,
           AVG(CASE WHEN status='served' AND called_at IS NOT NULL
                   THEN (julianday(called_at) - julianday(created_at)) * 24 * 60
                   ELSE NULL END) AS avg_wait
    FROM queue
    WHERE {where}
    GROUP BY lbl ORDER BY lbl
"""

_PEAK_SQL = """
    SELECT strftime('%H', {ca}) AS hour, COUNT(*) AS total
    FROM queue WHERE {where}
    GROUP BY hour ORDER BY hour
"""


async def get_stats_daily(date_str: str, tz_offset: float = 0.0) -> dict:
    """Hourly breakdown for a single calendar date (YYYY-MM-DD)."""
    ca = _tz_expr("created_at", tz_offset)
    where = f"strftime('%Y-%m-%d', {ca}) = ?"
    params = (date_str,)
    labels_all = [f"{h:02d}" for h in range(24)]

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            _CHART_SQL.format(lbl_expr=f"strftime('%H', {ca})", where=where), params
        ) as cur:
            rows = await cur.fetchall()
        async with db.execute(_PEAK_SQL.format(ca=ca, where=where), params) as cur:
            peak_rows = await cur.fetchall()

    return _make_stats_result(rows, labels_all, peak_rows)


async def get_stats_monthly(year: int, month: int, tz_offset: float = 0.0) -> dict:
    """Daily breakdown for a given year+month."""
    import calendar as _cal
    ca = _tz_expr("created_at", tz_offset)
    where = f"strftime('%Y', {ca}) = ? AND strftime('%m', {ca}) = ?"
    params = (str(year).zfill(4), str(month).zfill(2))
    days_in_month = _cal.monthrange(year, month)[1]
    labels_all = [f"{d:02d}" for d in range(1, days_in_month + 1)]

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            _CHART_SQL.format(lbl_expr=f"strftime('%d', {ca})", where=where), params
        ) as cur:
            rows = await cur.fetchall()
        async with db.execute(_PEAK_SQL.format(ca=ca, where=where), params) as cur:
            peak_rows = await cur.fetchall()

    return _make_stats_result(rows, labels_all, peak_rows)


# ── Messenger helpers ─────────────────────────────────────────────────────────

async def save_messenger_sub(psid: str, queue_number: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO messenger_subscriptions (psid, queue_number)
               VALUES (?, ?)
               ON CONFLICT(psid) DO UPDATE SET queue_number = excluded.queue_number,
                                               subscribed_at = datetime('now')""",
            (psid, queue_number),
        )
        await db.commit()


async def delete_messenger_sub(psid: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM messenger_subscriptions WHERE psid = ?", (psid,)
        )
        await db.commit()


async def get_messenger_subs(queue_number: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT psid FROM messenger_subscriptions WHERE queue_number = ?",
            (queue_number,),
        ) as cur:
            rows = await cur.fetchall()
    return [r[0] for r in rows]


async def get_stats_yearly(year: int, tz_offset: float = 0.0) -> dict:
    """Monthly breakdown for a given year."""
    ca = _tz_expr("created_at", tz_offset)
    where = f"strftime('%Y', {ca}) = ?"
    params = (str(year).zfill(4),)
    labels_all = [f"{m:02d}" for m in range(1, 13)]

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            _CHART_SQL.format(lbl_expr=f"strftime('%m', {ca})", where=where), params
        ) as cur:
            rows = await cur.fetchall()
        async with db.execute(_PEAK_SQL.format(ca=ca, where=where), params) as cur:
            peak_rows = await cur.fetchall()

    return _make_stats_result(rows, labels_all, peak_rows)

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app import database as db
from app.routers.auth import require_auth
from app.time_sync import time_sync

router = APIRouter(prefix="/api/stats", tags=["stats"])


async def _local_now() -> datetime:
    tz_offset = float(await db.get_setting("timezone", "0") or "0")
    return time_sync.now_utc() + timedelta(hours=tz_offset)


@router.get("/daily", dependencies=[Depends(require_auth)])
async def stats_daily(date_str: str = Query(default=None, alias="date")):
    """Hourly breakdown for a single calendar date (default: today in configured timezone)."""
    if date_str is None:
        date_str = (await _local_now()).date().isoformat()
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    tz_offset = float(await db.get_setting("timezone", "0") or "0")
    return await db.get_stats_daily(date_str, tz_offset=tz_offset)


@router.get("/monthly", dependencies=[Depends(require_auth)])
async def stats_monthly(
    year: int = Query(default=None),
    month: int = Query(default=None),
):
    """Daily breakdown for a given year and month (default: current month in configured timezone)."""
    now = await _local_now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12.")
    tz_offset = float(await db.get_setting("timezone", "0") or "0")
    return await db.get_stats_monthly(year, month, tz_offset=tz_offset)


@router.get("/yearly", dependencies=[Depends(require_auth)])
async def stats_yearly(year: int = Query(default=None)):
    """Monthly breakdown for a given year (default: current year in configured timezone)."""
    if year is None:
        year = (await _local_now()).year
    tz_offset = float(await db.get_setting("timezone", "0") or "0")
    return await db.get_stats_yearly(year, tz_offset=tz_offset)

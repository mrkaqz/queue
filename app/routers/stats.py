from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, Query

from app import database as db
from app.routers.auth import require_auth

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _default_date() -> str:
    return date.today().isoformat()


def _current_year() -> int:
    return datetime.now().year


def _current_month() -> int:
    return datetime.now().month


@router.get("/daily", dependencies=[Depends(require_auth)])
async def stats_daily(date_str: str = Query(default=None, alias="date")):
    """Hourly breakdown for a single calendar date (default: today)."""
    if date_str is None:
        date_str = _default_date()
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    return await db.get_stats_daily(date_str)


@router.get("/monthly", dependencies=[Depends(require_auth)])
async def stats_monthly(
    year: int = Query(default=None),
    month: int = Query(default=None),
):
    """Daily breakdown for a given year and month (default: current month)."""
    if year is None:
        year = _current_year()
    if month is None:
        month = _current_month()
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12.")
    return await db.get_stats_monthly(year, month)


@router.get("/yearly", dependencies=[Depends(require_auth)])
async def stats_yearly(year: int = Query(default=None)):
    """Monthly breakdown for a given year (default: current year)."""
    if year is None:
        year = _current_year()
    return await db.get_stats_yearly(year)

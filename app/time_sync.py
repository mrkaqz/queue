import asyncio
import ntplib
from datetime import datetime, timezone, timedelta


class TimeSyncManager:
    def __init__(self):
        self._offset: float = 0.0  # seconds: ntp_time - system_time

    def now_utc(self) -> datetime:
        """Current UTC time, NTP-corrected."""
        return datetime.now(timezone.utc) + timedelta(seconds=self._offset)

    def utc_iso(self) -> str:
        """UTC string for DB storage: '2026-03-13 11:07:00'."""
        return self.now_utc().strftime("%Y-%m-%d %H:%M:%S")

    async def sync(self) -> None:
        try:
            c = ntplib.NTPClient()
            resp = await asyncio.to_thread(c.request, "pool.ntp.org", version=3)
            self._offset = resp.offset
            print(f"[NTP] Synced. Offset: {self._offset:+.3f}s")
        except Exception as e:
            print(f"[NTP] Sync failed (using system clock): {e}")


time_sync = TimeSyncManager()

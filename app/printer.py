"""
ESC/POS ticket printer — raw TCP (port 9100).

Replicates exactly the print format used by the ESP32 Queue Ticket Printer device.
Runs the blocking socket I/O in a thread executor so it never blocks the async server.
"""

import asyncio
import socket
from datetime import datetime, timezone, timedelta

ESC = b'\x1b'
GS  = b'\x1d'


async def print_ticket(number: int, shop_name: str, ip: str, port: int = 9100, tz_offset: int = 0) -> None:
    """Send an ESC/POS queue ticket to the Xprinter over TCP (non-blocking).
    tz_offset: UTC offset in hours (e.g. 7 for Bangkok UTC+7)."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _print_sync, number, shop_name, ip, port, tz_offset)


def _safe_ascii(text: str) -> bytes:
    """Encode text to ASCII, stripping any non-ASCII characters (e.g. Thai).
    ESC/POS thermal printers only support ASCII/Latin — multi-byte UTF-8 causes
    garbled output. Falls back to '?' for any unencodable character."""
    return text.encode('ascii', errors='replace') + b'\n'


def _print_sync(number: int, shop_name: str, ip: str, port: int, tz_offset: int = 0) -> None:
    """Blocking ESC/POS send — called from a thread executor."""
    try:
        local_now = datetime.now(timezone.utc) + timedelta(hours=tz_offset)
        with socket.create_connection((ip, port), timeout=5) as s:
            def w(b: bytes) -> None:
                s.sendall(b)

            w(ESC + b'@')             # init printer
            w(ESC + b'a\x01')         # center alignment
            w(ESC + b'!\x08')         # bold, normal height
            w(_safe_ascii(shop_name))  # ASCII only — Thai/non-Latin causes garbled output
            w(ESC + b'!\x00')         # normal
            w(b'- Queue No. -\n')
            w(ESC + b'!\x30')         # double-width + double-height + bold
            w(f'{number:03d}\n'.encode())
            w(ESC + b'!\x00')         # normal
            w(local_now.strftime('%d/%m/%Y %H:%M\n').encode())
            w(b'\n\n\n\n\n\n')        # extra feeds so the cut clears the last printed line
            w(GS + b'V\x01')          # partial cut

        print(f'[printer] Ticket {number:03d} sent to {ip}:{port}')
    except OSError as exc:
        print(f'[printer] ERROR — could not print ticket {number:03d} to {ip}:{port}: {exc}')

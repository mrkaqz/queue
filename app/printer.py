"""
ESC/POS ticket printer — raw TCP (port 9100).

Replicates exactly the print format used by the ESP32 Queue Ticket Printer device.
Runs the blocking socket I/O in a thread executor so it never blocks the async server.
"""

import asyncio
import socket
from datetime import datetime

ESC = b'\x1b'
GS  = b'\x1d'


async def print_ticket(number: int, shop_name: str, ip: str, port: int = 9100) -> None:
    """Send an ESC/POS queue ticket to the Xprinter over TCP (non-blocking)."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _print_sync, number, shop_name, ip, port)


def _print_sync(number: int, shop_name: str, ip: str, port: int) -> None:
    """Blocking ESC/POS send — called from a thread executor."""
    try:
        with socket.create_connection((ip, port), timeout=5) as s:
            def w(b: bytes) -> None:
                s.sendall(b)

            w(ESC + b'@')             # init printer
            w(ESC + b'a\x01')         # center alignment
            w(ESC + b'!\x08')         # bold, normal height
            w(shop_name.encode('utf-8', errors='replace') + b'\n')
            w(ESC + b'!\x00')         # normal
            w(b'- Queue No. -\n')
            w(ESC + b'!\x30')         # double-width + double-height + bold
            w(f'{number:03d}\n'.encode())
            w(ESC + b'!\x00')         # normal
            w(datetime.now().strftime('%d/%m/%Y %H:%M\n').encode())
            w(b'\n')
            w(GS + b'V\x01')          # partial cut

        print(f'[printer] Ticket {number:03d} sent to {ip}:{port}')
    except OSError as exc:
        print(f'[printer] ERROR — could not print ticket {number:03d} to {ip}:{port}: {exc}')

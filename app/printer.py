"""
ESC/POS ticket printer — raw TCP (port 9100).

Normal size: ESC ! character mode (compact, fast).
Large size:  GS v 0 raster mode — renders the queue number with a
             TrueType font via Pillow so edges are smooth at 203 DPI.

Runs all blocking socket/image work in a thread executor so it never
blocks the async server.
"""

import asyncio
import os
import socket
import struct
from datetime import datetime, timezone, timedelta

ESC = b'\x1b'
GS  = b'\x1d'

# TrueType font search order (installed by fonts-dejavu-core in the Dockerfile)
_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

_font_path_cache: str | None = None
_font_path_searched: bool = False

# Font cache: (font_path, paper_dots, str_len) → ImageFont
# The 3-digit format {:03d} means every queue number has the same char
# count, so the same font size is reused for all tickets after the first.
_font_cache: dict = {}


def _get_font_path() -> str | None:
    """Return the first available TrueType bold font path (cached)."""
    global _font_path_cache, _font_path_searched
    if not _font_path_searched:
        for p in _FONT_PATHS:
            if os.path.exists(p):
                _font_path_cache = p
                break
        _font_path_searched = True
    return _font_path_cache


def _render_number_raster(number_str: str, paper_dots: int = 384) -> bytes:
    """
    Render number_str as an ESC/POS GS v 0 raster image using a TrueType font.
    Returns empty bytes if Pillow or a suitable font is unavailable
    (caller falls back to bitmap scaling).

    Performance notes
    -----------------
    • Font size is computed once and cached — subsequent tickets skip the
      size-search loop entirely.
    • Pixel packing uses PIL's native tobytes() (C-level) instead of a
      Python triple-loop — ~100× faster, negligible overhead on any ticket.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return b""

    font_path = _get_font_path()
    if font_path is None:
        return b""

    # Cache key: same paper width + same string length → same font size
    cache_key = (font_path, paper_dots, len(number_str))
    chosen_font = _font_cache.get(cache_key)

    if chosen_font is None:
        # First ticket: find the largest size that fits ~88% of paper width
        TARGET_W = int(paper_dots * 0.88)
        probe_canvas = Image.new("L", (paper_dots * 4, 600), 255)
        probe_draw = ImageDraw.Draw(probe_canvas)
        for size in range(260, 20, -4):
            try:
                f = ImageFont.truetype(font_path, size)
            except OSError:
                continue
            bb = probe_draw.textbbox((0, 0), number_str, font=f)
            if (bb[2] - bb[0]) <= TARGET_W:
                chosen_font = f
                break
        if chosen_font is None:
            return b""
        _font_cache[cache_key] = chosen_font

    # Measure final bounding box with the cached font
    probe = Image.new("L", (paper_dots * 2, 600), 255)
    bb = ImageDraw.Draw(probe).textbbox((0, 0), number_str, font=chosen_font)
    text_w = bb[2] - bb[0]
    text_h = bb[3] - bb[1]

    # Render grayscale (anti-aliased) then threshold to 1-bit.
    # Invert so dark (text) pixels become 255 in mode '1' → bit=1 in tobytes()
    # ESC/POS GS v 0: bit=1 = print a black dot ✓
    PAD = 18
    img_gray = Image.new("L", (paper_dots, text_h + PAD * 2), 255)
    x = (paper_dots - text_w) // 2 - bb[0]
    y = PAD - bb[1]
    ImageDraw.Draw(img_gray).text((x, y), number_str, font=chosen_font, fill=0)
    img = img_gray.point(lambda p: 255 if p < 128 else 0, "1")

    # PIL '1' tobytes(): packs 8 pixels/byte MSB-first; nonzero pixel → bit=1
    # 384 px / 8 = 48 bytes/row exactly → no padding, tobytes() is the raw bits
    bpl = paper_dots // 8
    raw = img.tobytes()

    # GS v 0 command: GS v 0 m xL xH yL yH [data]
    return (
        b"\x1d\x76\x30\x00"                      # GS v 0, m=0 (normal density)
        + struct.pack("<HH", bpl, img.height)
        + raw
    )


async def print_ticket(number: int, shop_name: str, ip: str, port: int = 9100,
                       tz_offset: int = 0, size: str = "normal") -> None:
    """Send an ESC/POS queue ticket to the Xprinter over TCP (non-blocking).

    tz_offset : UTC offset in whole hours (e.g. 7 for Bangkok UTC+7).
    size      : 'normal' or 'large'.  Large renders the queue number as a
                smooth TrueType raster image using Pillow + DejaVu Sans Bold.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _print_sync, number, shop_name, ip, port, tz_offset, size)


def _safe_ascii(text: str) -> bytes:
    """Encode text to ASCII, replacing any non-ASCII character with '?'.
    ESC/POS thermal printers only support single-byte code pages —
    multi-byte UTF-8 (e.g. Thai) causes garbled output."""
    return text.encode("ascii", errors="replace") + b"\n"


def _print_sync(number: int, shop_name: str, ip: str, port: int,
                tz_offset: int = 0, size: str = "normal") -> None:
    """Blocking ESC/POS send — called from a thread executor."""
    try:
        local_now = datetime.now(timezone.utc) + timedelta(hours=tz_offset)
        with socket.create_connection((ip, port), timeout=5) as s:
            def w(b: bytes) -> None:
                s.sendall(b)

            w(ESC + b"@")          # init printer
            w(ESC + b"a\x01")      # center alignment

            if size == "large":
                # ── Large ticket — TrueType raster number ────────────────────
                w(ESC + b"!\x08")              # bold, normal height
                w(_safe_ascii(shop_name))
                w(ESC + b"!\x00")              # normal
                w(b"\n")
                w(b"- Queue No. -\n")
                w(b"\n")
                raster = _render_number_raster(f"{number}")
                if raster:
                    w(raster)                  # smooth TrueType image
                else:
                    # Pillow/font not available — fall back to bitmap scale
                    w(GS  + b"!\x55")          # 6× height × 6× width
                    w(f"{number}\n".encode())
                    w(GS  + b"!\x00")
                w(b"\n")
                w(local_now.strftime("%d/%m/%Y %H:%M\n").encode())

            else:
                # ── Normal ticket — fast ESC/POS character mode ───────────────
                w(ESC + b"!\x08")              # bold, normal height
                w(_safe_ascii(shop_name))
                w(ESC + b"!\x00")              # normal
                w(b"- Queue No. -\n")
                w(ESC + b"!\x30")              # double-width + double-height
                w(f"{number}\n".encode())
                w(ESC + b"!\x00")              # normal
                w(local_now.strftime("%d/%m/%Y %H:%M\n").encode())

            w(b"\n\n\n\n\n\n")     # extra feed so the cutter clears the last line
            w(GS + b"V\x01")       # partial cut

        print(f"[printer] Ticket {number:03d} ({size}) sent to {ip}:{port}")
    except OSError as exc:
        print(f"[printer] ERROR — could not print ticket {number:03d} to {ip}:{port}: {exc}")

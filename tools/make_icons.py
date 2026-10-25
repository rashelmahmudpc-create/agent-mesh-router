#!/usr/bin/env python3
"""🎨 আইকন বানানোর ছোট স্ক্রিপ্ট (PIL লাগে না — শুধু zlib + struct)।

    python3 tools/make_icons.py

তৈরি করে:
    web/icons/icon-180.png   (iPhone হোম স্ক্রিন)
    web/icons/icon-192.png   (PWA)
    web/icons/icon-512.png   (PWA)
    web/icons/icon-maskable-512.png (Android maskable)
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web" / "icons"

TOP = (25, 195, 125)
BOTTOM = (11, 122, 92)
WHITE = (255, 255, 255)
DOT = (11, 122, 92)


def _lerp(a: int, b: int, t: float) -> float:
    return a + (b - a) * t


def _rounded_rect(px: float, py: float, x0: float, y0: float, x1: float, y1: float, r: float) -> float:
    """ভেতরে থাকলে ঋণাত্মক, বাইরে ধনাত্মক (signed distance)।"""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 - r, (y1 - y0) / 2 - r
    dx = abs(px - cx) - hx
    dy = abs(py - cy) - hy
    outside = math.hypot(max(dx, 0.0), max(dy, 0.0))
    inside = min(max(dx, dy), 0.0)
    return outside + inside - r


def _in_tail(px: float, py: float, scale: float) -> bool:
    """বেলুনের নিচের ছোট লেজ (ত্রিভুজ)।"""
    # ত্রিভুজ: (150,300) → (150,372) → (222,300)
    ax, ay, bx, by, cx, cy = 150 * scale, 300 * scale, 150 * scale, 380 * scale, 230 * scale, 300 * scale
    d1 = (px - bx) * (ay - by) - (ax - bx) * (py - by)
    d2 = (px - cx) * (by - cy) - (bx - cx) * (py - cy)
    d3 = (px - ax) * (cy - ay) - (cx - ax) * (py - ay)
    neg = d1 < 0 or d2 < 0 or d3 < 0
    pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (neg and pos)


def _pixel(nx: float, ny: float, scale: float) -> tuple[int, int, int, int]:
    """nx, ny = 0..1 স্বাভাবিক স্থানাঙ্ক।"""
    t = min(max(ny, 0.0), 1.0)
    base = (
        int(_lerp(TOP[0], BOTTOM[0], t)),
        int(_lerp(TOP[1], BOTTOM[1], t)),
        int(_lerp(TOP[2], BOTTOM[2], t)),
    )
    px, py = nx * 512.0, ny * 512.0

    # 🫧 বেলুন
    bubble = _rounded_rect(px, py, 104 * scale, 118 * scale, 408 * scale, 344 * scale, 58 * scale)
    inside = bubble < 0 or _in_tail(px, py, scale)
    if not inside:
        return (*base, 255)

    # ⚪️ ভেতরের তিনটা বিন্দু
    for cx in (184, 256, 328):
        if math.hypot(px - cx * scale, py - 232 * scale) < 24 * scale:
            return (*DOT, 255)
    return (*WHITE, 255)


def make(size: int, scale: float = 1.0, supersample: int = 2) -> bytes:
    rows = []
    step = 1.0 / (size * supersample)
    for y in range(size):
        row = bytearray()
        for x in range(size):
            r = g = b = a = 0
            for sy in range(supersample):
                for sx in range(supersample):
                    nx = (x * supersample + sx + 0.5) / (size * supersample)
                    ny = (y * supersample + sy + 0.5) / (size * supersample)
                    pr, pg, pb, pa = _pixel(nx, ny, scale)
                    r += pr
                    g += pg
                    b += pb
                    a += pa
            n = supersample * supersample
            row += bytes((r // n, g // n, b // n, a // n))
        rows.append(row)
    _ = step
    return _png(size, size, rows)


def _png(width: int, height: int, rows: list[bytearray]) -> bytes:
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("icon-180.png", 180, 1.0),
        ("icon-192.png", 192, 1.0),
        ("icon-512.png", 512, 1.0),
        ("icon-maskable-512.png", 512, 0.78),
    ]
    for name, size, scale in jobs:
        data = make(size, scale=scale)
        (OUT / name).write_bytes(data)
        print(f"✅ {name} — {size}×{size}, {len(data) // 1024} KB")


if __name__ == "__main__":
    main()

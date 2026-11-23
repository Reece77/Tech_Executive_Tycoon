"""Draws packaging/icon.ico (M58): three rising bars in the game's accent blue on its dark
panel colour, as PNG images inside an ICO at 16-256 px. Standard library only; rerun after
changing the drawing: `python packaging/make_icon.py`."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

SIZES = (16, 24, 32, 48, 64, 128, 256)
BG = (0x1A, 0x1B, 0x1E)
ACCENT = (0x5A, 0xA2, 0xFF)  # --tst-accent
BARS = ((0.18, 0.36, 0.55), (0.40, 0.58, 0.40), (0.62, 0.80, 0.22))  # x0, x1, top (of 1)
BOTTOM = 0.80
RADIUS = 0.18


def _inside_rounded(x: float, y: float) -> bool:
    r = RADIUS
    cx = min(max(x, r), 1 - r)
    cy = min(max(y, r), 1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _pixel(x: float, y: float) -> tuple[int, int, int, int]:
    if not _inside_rounded(x, y):
        return 0, 0, 0, 0
    for x0, x1, top in BARS:
        if x0 <= x < x1 and top <= y < BOTTOM:
            return (*ACCENT, 255)
    return (*BG, 255)


def png(size: int) -> bytes:
    rows = []
    samples = 4  # 4x4 supersampling for smooth edges
    for py in range(size):
        row = bytearray(b"\x00")
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(samples):
                for sx in range(samples):
                    p = _pixel(
                        (px + (sx + 0.5) / samples) / size, (py + (sy + 0.5) / samples) / size
                    )
                    for i in range(4):
                        acc[i] += p[i] * (p[3] if i < 3 else 255)
            alpha = acc[3] / (255 * samples * samples)
            if alpha:
                rgb = [round(acc[i] / (alpha * samples * samples)) for i in range(3)]
            else:
                rgb = [0, 0, 0]
            row += bytes([*rgb, round(alpha)])
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


def ico(sizes: tuple[int, ...] = SIZES) -> bytes:
    images = [png(s) for s in sizes]
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for size, data in zip(sizes, images, strict=True):
        dim = 0 if size >= 256 else size
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return out + b"".join(images)


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "icon.ico"
    target.write_bytes(ico())
    print(f"wrote {target}")

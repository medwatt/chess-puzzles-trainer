from __future__ import annotations

import binascii
import struct
import zlib

from chess_puzzles.ui.icon_recolor import recolor_png_bytes


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_recolor_png_bytes_preserves_alpha_and_recolors_visible_pixels() -> None:
    source = _rgba_png(
        width=2,
        height=1,
        pixels=bytes(
            (
                0,
                0,
                0,
                255,
                0,
                0,
                0,
                0,
            )
        ),
    )

    recolored = recolor_png_bytes(source, "#f8f8f2")
    pixels = _rgba_pixels(recolored)

    assert pixels == bytes(
        (
            248,
            248,
            242,
            255,
            0,
            0,
            0,
            0,
        )
    )


def _rgba_png(width: int, height: int, pixels: bytes) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + pixels[y * width * 4 : (y + 1) * width * 4] for y in range(height))
    return PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


def _rgba_pixels(data: bytes) -> bytes:
    assert data.startswith(PNG_SIGNATURE)
    offset = len(PNG_SIGNATURE)
    width = 0
    height = 0
    idat = bytearray()
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height = struct.unpack(">II", chunk_data[:8])
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            break
    raw = zlib.decompress(bytes(idat))
    rows = []
    row_bytes = width * 4
    for y in range(height):
        start = y * (row_bytes + 1)
        assert raw[start] == 0
        rows.append(raw[start + 1 : start + 1 + row_bytes])
    return b"".join(rows)


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(chunk_type)
    crc = binascii.crc32(data, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

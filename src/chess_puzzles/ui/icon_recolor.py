from __future__ import annotations

import base64
import binascii
import struct
import tkinter as tk
import zlib
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
COLOR_TYPE_RGB = 2
COLOR_TYPE_GRAYSCALE_ALPHA = 4
COLOR_TYPE_RGBA = 6


class PngRecolorError(ValueError):
    pass


class RecoloredIconCache:
    def __init__(self) -> None:
        self._cache: dict[tuple[Path, str], tk.PhotoImage] = {}

    def image_for(self, path: Path, color: str) -> tk.PhotoImage | None:
        key = (path, normalize_hex_color(color))
        if key in self._cache:
            return self._cache[key]
        try:
            data = recolored_png_bytes(path, key[1])
            image = tk.PhotoImage(data=base64.b64encode(data).decode("ascii"), format="png")
        except (OSError, PngRecolorError, tk.TclError):
            return None
        self._cache[key] = image
        return image

    def clear(self) -> None:
        self._cache.clear()


def recolored_png_bytes(path: Path, color: str) -> bytes:
    return recolor_png_bytes(path.read_bytes(), color)


def recolor_png_bytes(data: bytes, color: str) -> bytes:
    target = _rgb_tuple(normalize_hex_color(color))
    width, height, bit_depth, color_type, chunks, image_data = _read_png(data)
    if bit_depth != 8:
        raise PngRecolorError("Only 8-bit PNG icons can be recolored")
    if color_type not in {COLOR_TYPE_RGB, COLOR_TYPE_GRAYSCALE_ALPHA, COLOR_TYPE_RGBA}:
        raise PngRecolorError("Only RGB/RGBA PNG icons can be recolored")

    channels = _channels_for_color_type(color_type)
    row_bytes = width * channels
    raw = zlib.decompress(image_data)
    pixels = _unfilter_scanlines(raw, width, height, channels)
    recolored = bytearray()
    for y in range(height):
        start = y * row_bytes
        row = bytearray(pixels[start : start + row_bytes])
        for x in range(width):
            offset = x * channels
            if _pixel_visible(row, offset, channels, color_type):
                _set_pixel_rgb(row, offset, channels, color_type, target)
        recolored.append(0)
        recolored.extend(row)

    return _write_png(chunks, zlib.compress(bytes(recolored)))


def normalize_hex_color(color: str) -> str:
    value = color.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) == 3:
        value = "".join(character * 2 for character in value)
    if len(value) != 6:
        raise PngRecolorError(f"Unsupported color value: {color}")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PngRecolorError(f"Unsupported color value: {color}") from exc
    return f"#{value.lower()}"


def _read_png(data: bytes) -> tuple[int, int, int, int, list[tuple[bytes, bytes]], bytes]:
    if not data.startswith(PNG_SIGNATURE):
        raise PngRecolorError("Not a PNG file")
    chunks: list[tuple[bytes, bytes]] = []
    idat_parts: list[bytes] = []
    width = height = bit_depth = color_type = 0
    offset = len(PNG_SIGNATURE)
    while offset < len(data):
        if offset + 8 > len(data):
            raise PngRecolorError("Malformed PNG chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        crc = data[offset + 8 + length : offset + 12 + length]
        if len(chunk_data) != length or len(crc) != 4:
            raise PngRecolorError("Truncated PNG chunk")
        expected_crc = binascii.crc32(chunk_type)
        expected_crc = binascii.crc32(chunk_data, expected_crc) & 0xFFFFFFFF
        if expected_crc != struct.unpack(">I", crc)[0]:
            raise PngRecolorError("PNG CRC mismatch")
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = _read_ihdr(chunk_data)
            chunks.append((chunk_type, chunk_data))
        elif chunk_type == b"IDAT":
            idat_parts.append(chunk_data)
        elif chunk_type != b"IEND":
            chunks.append((chunk_type, chunk_data))
        if chunk_type == b"IEND":
            break
        offset += 12 + length
    if not width or not height or not idat_parts:
        raise PngRecolorError("PNG is missing image data")
    return width, height, bit_depth, color_type, chunks, b"".join(idat_parts)


def _read_ihdr(data: bytes) -> tuple[int, int, int, int]:
    if len(data) != 13:
        raise PngRecolorError("Invalid PNG header")
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", data)
    if compression != 0 or filter_method != 0 or interlace != 0:
        raise PngRecolorError("Interlaced or non-standard PNG icons are not supported")
    return width, height, bit_depth, color_type


def _write_png(chunks: list[tuple[bytes, bytes]], image_data: bytes) -> bytes:
    output = bytearray(PNG_SIGNATURE)
    ihdr = next((data for chunk_type, data in chunks if chunk_type == b"IHDR"), None)
    if ihdr is not None:
        output.extend(_chunk(b"IHDR", ihdr))
    for chunk_type, chunk_data in chunks:
        if chunk_type not in {b"IHDR", b"IDAT"}:
            output.extend(_chunk(chunk_type, chunk_data))
    output.extend(_chunk(b"IDAT", image_data))
    output.extend(_chunk(b"IEND", b""))
    return bytes(output)


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(chunk_type)
    crc = binascii.crc32(data, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def _unfilter_scanlines(raw: bytes, width: int, height: int, channels: int) -> bytes:
    row_bytes = width * channels
    expected_size = height * (row_bytes + 1)
    if len(raw) != expected_size:
        raise PngRecolorError("Unexpected PNG data size")
    output = bytearray(height * row_bytes)
    source = 0
    for y in range(height):
        filter_type = raw[source]
        source += 1
        row = bytearray(raw[source : source + row_bytes])
        source += row_bytes
        previous_start = (y - 1) * row_bytes
        for index in range(row_bytes):
            left = row[index - channels] if index >= channels else 0
            above = output[previous_start + index] if y > 0 else 0
            upper_left = output[previous_start + index - channels] if y > 0 and index >= channels else 0
            if filter_type == 1:
                row[index] = (row[index] + left) & 0xFF
            elif filter_type == 2:
                row[index] = (row[index] + above) & 0xFF
            elif filter_type == 3:
                row[index] = (row[index] + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                row[index] = (row[index] + _paeth(left, above, upper_left)) & 0xFF
            elif filter_type != 0:
                raise PngRecolorError("Unsupported PNG filter")
        output[y * row_bytes : (y + 1) * row_bytes] = row
    return bytes(output)


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _channels_for_color_type(color_type: int) -> int:
    if color_type == COLOR_TYPE_RGB:
        return 3
    if color_type == COLOR_TYPE_GRAYSCALE_ALPHA:
        return 2
    if color_type == COLOR_TYPE_RGBA:
        return 4
    raise PngRecolorError("Unsupported PNG color type")


def _pixel_visible(row: bytearray, offset: int, channels: int, color_type: int) -> bool:
    if color_type in {COLOR_TYPE_GRAYSCALE_ALPHA, COLOR_TYPE_RGBA}:
        return row[offset + channels - 1] > 0
    return True


def _set_pixel_rgb(row: bytearray, offset: int, channels: int, color_type: int, rgb: tuple[int, int, int]) -> None:
    if color_type == COLOR_TYPE_GRAYSCALE_ALPHA:
        row[offset] = round(sum(rgb) / 3)
        return
    row[offset] = rgb[0]
    row[offset + 1] = rgb[1]
    row[offset + 2] = rgb[2]


def _rgb_tuple(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)

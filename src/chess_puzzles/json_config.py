from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_json_object(path: str | Path, *, error_message: str) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(error_message) from exc
    if not isinstance(data, dict):
        raise ValueError(error_message)
    return data


def int_value(
    data: dict[str, Any],
    key: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Read one integer setting, falling back to ``default`` when unusable.

    Strict on purpose: a JSON string or bool is a malformed settings file, not
    something to coerce. ``True`` is an ``int`` in Python, so it is rejected
    explicitly. Bounds clamp rather than reject, because an out-of-range number
    is still a legible intention."""
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def save_json_object(path: str | Path, data: dict[str, Any]) -> None:
    """Write JSON atomically so a crash mid-write cannot corrupt the file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_name(target.name + ".tmp")
    try:
        temp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, target)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise

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

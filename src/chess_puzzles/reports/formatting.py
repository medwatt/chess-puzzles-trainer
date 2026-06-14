from __future__ import annotations


def format_duration_ms(value: int | None) -> str:
    if value is None:
        return "-"
    seconds = max(0, value // 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

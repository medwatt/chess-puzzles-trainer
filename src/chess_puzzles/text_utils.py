from __future__ import annotations

import re


def clean_comment_text(comment: str) -> str:
    normalized = comment.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""
    paragraphs = re.split(r"\n\s*\n+", normalized)
    cleaned: list[str] = []
    for paragraph in paragraphs:
        text = re.sub(r"[ \t\f\v]+", " ", paragraph)
        text = re.sub(r"\s*\n\s*", " ", text)
        text = re.sub(r" {2,}", " ", text).strip()
        if text:
            cleaned.append(text)
    return "\n\n".join(cleaned)


def display_comment(comment: str, clean: bool) -> str:
    return clean_comment_text(comment) if clean else comment

from __future__ import annotations

import sys
from pathlib import Path

from chess_puzzles.platform.paths import assets_dir


def test_assets_dir_uses_pyinstaller_meipass(monkeypatch) -> None:
    bundle_root = Path("/tmp/chess-puzzles-bundle")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_root), raising=False)

    assert assets_dir() == bundle_root / "assets"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_DIR="$ROOT_DIR/build/pyinstaller"

cd "$ROOT_DIR"
mkdir -p "$SPEC_DIR"

python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name chess-puzzles-trainer \
  --specpath "$SPEC_DIR" \
  --workpath "$ROOT_DIR/build/pyinstaller/work" \
  --distpath "$ROOT_DIR/dist" \
  --paths src \
  --add-data "$ROOT_DIR/assets:assets" \
  --add-data "$ROOT_DIR/src/chess_puzzles/lichess/themes.txt:chess_puzzles/lichess" \
  src/chess_puzzles/__main__.py

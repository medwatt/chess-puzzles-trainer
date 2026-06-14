# powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1

$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $PSScriptRoot
$specDir = Join-Path $rootDir "build\pyinstaller"
Set-Location $rootDir
New-Item -ItemType Directory -Force -Path $specDir | Out-Null

python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onedir `
  --name chess-puzzles-trainer `
  --specpath $specDir `
  --workpath (Join-Path $rootDir "build\pyinstaller\work") `
  --distpath (Join-Path $rootDir "dist") `
  --paths src `
  --add-data "$rootDir\assets;assets" `
  --add-data "$rootDir\src\chess_puzzles\lichess\themes.txt;chess_puzzles\lichess" `
  src/chess_puzzles/__main__.py

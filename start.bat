@echo off
REM Start The Anything Converter (Windows)
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\pip install -q -r requirements.txt
)
where ffmpeg >nul 2>nul || echo LET OP: ffmpeg niet gevonden - video/audio werkt dan niet.
start "" http://localhost:8000
.venv\Scripts\python app.py

#!/usr/bin/env bash
# Start The Anything Converter (macOS / Linux)
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
command -v ffmpeg >/dev/null || echo "LET OP: ffmpeg niet gevonden - video/audio werkt dan niet."
(sleep 1.5 && (open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null) ) &
exec .venv/bin/python app.py

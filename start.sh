#!/usr/bin/env sh
# Analog Atlas: starts the local server (Atlas + API + data pipeline). Open http://127.0.0.1:8000/
cd "$(dirname "$0")/backend" || exit 1
python3 -m pip install -q -r requirements.txt
python3 -m uvicorn analog_atlas.server:app --host 127.0.0.1 --port 8000

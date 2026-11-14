@echo off
rem Analog Atlas: starts the local server (API + pipeline panel + app) and opens the panel.
cd /d "%~dp0backend"
python -m pip install -q -r requirements.txt
start "" http://127.0.0.1:8000/
python -m uvicorn analog_atlas.server:app --host 127.0.0.1 --port 8000
pause

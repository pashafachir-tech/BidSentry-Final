@echo off
setlocal
cd /d "%~dp0"
echo Starting BidSentry local workspace...
echo Open http://127.0.0.1:8000 after the server is ready.
echo Press Ctrl+C to stop.
if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv. Create it and install requirements.txt first.
  exit /b 1
)
".venv\Scripts\python.exe" server.py
endlocal

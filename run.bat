@echo off
cd /d %~dp0backend

if not exist .venv\Scripts\python.exe (
  echo The virtual environment is missing. Run setup.bat first.
  pause
  exit /b 1
)

echo FormaLang running at http://127.0.0.1:8000
echo Press Ctrl+C to stop.
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn app.main:app
pause
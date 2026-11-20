@echo off
cd /d %~dp0backend

if not exist .venv (
  py -3.14 -m venv .venv
  if errorlevel 1 (
    echo.
    echo Python 3.12 was not found. Install it from python.org, then run this again.
    pause
    exit /b 1
  )
)

.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 ( echo Dependency install failed. & pause & exit /b 1 )

if not exist .env copy .env.example .env >nul

.venv\Scripts\python.exe -m pytest
if errorlevel 1 ( echo. & echo Tests failed. & pause & exit /b 1 )

echo.
echo FormaLang running at http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
pause
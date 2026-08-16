@echo off
setlocal
cd /d "%~dp0"
echo Starting Behave AI Laboratory...

python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python 3 is required but was not found.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Preparing Behave for first launch...
    python -m venv .venv
    if errorlevel 1 goto :fail
)

".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 goto :fail

".venv\Scripts\python.exe" launch_behave.py
exit /b %errorlevel%

:fail
echo.
echo Behave setup failed. Check your internet connection and Python installation.
pause
exit /b 1

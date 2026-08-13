@echo off
echo Starting Behave AI Laboratory...

python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: python is not installed or not in your PATH.
    echo Please install Python 3 to run Behave.
    pause
    exit /b 1
)

echo Starting local demo agent (Agent v1 ^& v2)...
start /b python demo_agent.py

echo Starting Behave Dashboard...
start /b python app.py

echo Waiting for services to start...
timeout /t 2 /nobreak >nul

echo Opening dashboard...
start http://127.0.0.1:5000

echo Behave is running. Close this window to stop.
pause
taskkill /f /im python.exe >nul 2>&1

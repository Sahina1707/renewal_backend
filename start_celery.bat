@echo off
title Celery Worker & Beat Launcher

echo ======================================================
echo 🚀 Starting Celery Worker & Beat Services
echo ======================================================

:: Start Redis (update the path if needed)
echo Starting Redis...
start "" "C:\Program Files\Redis\redis-server.exe"
timeout /t 5 >nul

:: Activate virtual environment
echo Activating virtual environment...
call "C:\Users\Sahina1001\Downloads\Renewal_backend\venv\Scripts\activate.bat"

:: Start Celery Worker
echo Starting Celery Worker...
start "" cmd /k "celery -A renewal_backend worker --loglevel=info"

:: Start Celery Beat
echo Starting Celery Beat...
start "" cmd /k "celery -A renewal_backend beat --loglevel=info"

echo ======================================================
echo ✅ All Celery processes started successfully!
echo ======================================================

pause

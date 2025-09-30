@echo off
setlocal

:: Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found
    echo Please run install.bat first
    pause
    exit /b 1
)

:: Check if config file exists
if not exist "js8-mqtt-bridge.cfg" (
    echo ERROR: Configuration file js8-mqtt-bridge.cfg not found
    echo Please create and configure this file before running
    pause
    exit /b 1
)

echo Starting JS8-MQTT Bridge...
echo Press Ctrl+C to stop
echo.

:: Activate virtual environment and run
call "venv\Scripts\activate"
python js8-mqtt-bridge.py

pause
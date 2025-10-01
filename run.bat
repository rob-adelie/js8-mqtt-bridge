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

:: Use the virtual environment's Python directly (no need to activate)
echo Using virtual environment Python...
echo Checking if paho-mqtt is installed...
"venv\Scripts\python.exe" -c "import paho.mqtt.client; print('paho-mqtt is available')"
if errorlevel 1 (
    echo ERROR: paho-mqtt not found in virtual environment
    echo Please run install.bat again to reinstall requirements
    pause
    exit /b 1
)

echo Starting JS8-MQTT Bridge...
"venv\Scripts\python.exe" js8-mqtt-bridge.py

pause
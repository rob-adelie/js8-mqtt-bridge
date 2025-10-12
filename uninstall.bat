@echo off
setlocal

echo JS8-MQTT Bridge Uninstaller
echo.

:: Remove startup shortcut
set "startup_folder=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "shortcut_name=js8-mqtt-bridge.lnk"

if exist "%startup_folder%\%shortcut_name%" (
    echo Removing startup shortcut...
    del "%startup_folder%\%shortcut_name%"
    echo ✓ Startup shortcut removed
) else (
    echo No startup shortcut found
)

:: Ask about removing virtual environment
echo.
set /p "remove_venv=Remove virtual environment? (y/N): "
if /i "%remove_venv%"=="y" (
    if exist "venv" (
        echo Removing virtual environment...
        rmdir /s /q "venv"
        echo ✓ Virtual environment removed
    )
)

:: Ask about removing logs
echo.
set /p "remove_logs=Remove logs folder? (y/N): "
if /i "%remove_logs%"=="y" (
    if exist "logs" (
        echo Removing logs...
        rmdir /s /q "logs"
        echo ✓ Logs removed
    )
)

echo.
echo Uninstall complete!
echo The Python script and config files remain for manual cleanup if needed.
pause
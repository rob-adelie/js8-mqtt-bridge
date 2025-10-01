@echo off
setlocal

:: Check if Python is installed
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

:: Use current directory instead of assuming path
set "project_dir=%~dp0"
set "python_script_name=js8-mqtt-bridge.py"

:: Check if we're in the right directory
if not exist "%python_script_name%" (
    echo ERROR: %python_script_name% not found in current directory
    echo Please run this script from the js8-mqtt-bridge directory
    pause
    exit /b 1
)

echo Found project directory: %project_dir%
echo.

:: --- Installation Steps ---

:: Create a virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

:: Activate the virtual environment
echo Activating virtual environment...
call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

:: Verify activation worked by checking if pip is available
echo Verifying virtual environment activation...
echo Current PATH: %PATH%
echo.
where pip >nul 2>&1
if errorlevel 1 (
    echo WARNING: pip not found in PATH after activation, trying direct path...
    echo Checking if pip exists in venv\Scripts...
    if exist "venv\Scripts\pip.exe" (
        echo Found pip.exe in venv\Scripts, using direct path...
        "venv\Scripts\pip.exe" install --no-cache-dir -r requirements.txt
        if errorlevel 1 (
            echo ERROR: Failed to install requirements using direct pip path
            pause
            exit /b 1
        )
    ) else (
        echo ERROR: pip.exe not found in venv\Scripts directory
        echo Available files in venv\Scripts:
        dir "venv\Scripts" /b
        pause
        exit /b 1
    )
) else (
    :: Install the pip requirements using pip from PATH
    echo Installing requirements using pip from PATH...
    pip install --no-cache-dir -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install requirements
        pause
        exit /b 1
    )
)

:: Create a logs folder
echo Creating logs folder...
if not exist "logs" mkdir logs

:: --- Create the Startup Shortcut ---

:: Define the path to the user's startup folder
set "startup_folder=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "shortcut_name=js8-mqtt-bridge.lnk"

:: Check if shortcut already exists
if exist "%startup_folder%\%shortcut_name%" (
    echo Startup shortcut already exists. Removing old one...
    del "%startup_folder%\%shortcut_name%"
)

:: Find the python executable from the virtual environment
set "venv_python_exe=%project_dir%\venv\Scripts\pythonw.exe"

:: Create the VBScript to make the shortcut
echo Creating startup shortcut...
echo Set oShell = WScript.CreateObject("WScript.Shell") > create_shortcut.vbs
echo Set oShortcut = oShell.CreateShortcut("%startup_folder%\%shortcut_name%") >> create_shortcut.vbs
echo oShortcut.TargetPath = "%venv_python_exe%" >> create_shortcut.vbs
echo oShortcut.Arguments = "%project_dir%\%python_script_name%" >> create_shortcut.vbs
echo oShortcut.WorkingDirectory = "%project_dir%" >> create_shortcut.vbs
echo oShortcut.Description = "JS8-MQTT Bridge" >> create_shortcut.vbs
echo oShortcut.Save >> create_shortcut.vbs

cscript //nologo create_shortcut.vbs
if errorlevel 1 (
    echo WARNING: Failed to create startup shortcut
) else (
    echo Startup shortcut created successfully
)
del create_shortcut.vbs

:: --- Verification ---
echo.
echo Verifying installation...
if exist "venv\Scripts\python.exe" (
    echo ✓ Virtual environment created
) else (
    echo ✗ Virtual environment missing
)

if exist "logs" (
    echo ✓ Logs directory created
) else (
    echo ✗ Logs directory missing
)

if exist "%startup_folder%\%shortcut_name%" (
    echo ✓ Startup shortcut created
) else (
    echo ✗ Startup shortcut missing
)

echo.
echo Installation complete!
echo.
echo IMPORTANT: You need to configure js8-mqtt-bridge.cfg before running
echo The bridge will start automatically on your next login
echo.
echo To test now, run: run.bat
echo To uninstall, run: uninstall.bat
echo.
pause
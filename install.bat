@echo off
setlocal

:: Define the path to the project directory
set "project_dir=%USERPROFILE%\Projects\js8-mqtt-bridge"
set "python_script_name=js8-mqtt-bridge.py"

:: Check if the project directory exists, and if not, create it
if not exist "%project_dir%" (
    echo The project directory does not exist. Please run this script from the correct location.
    pause
    exit /b 1
)

:: Go into the project directory
cd /d "%project_dir%"

:: --- Installation Steps ---

:: Create a virtual environment
echo Creating virtual environment...
python -m venv venv

:: Activate the virtual environment. Note: `source` is for Linux. On Windows, you call the activation script.
echo Activating virtual environment...
call "venv\Scripts\activate"

:: Install the pip requirements
echo Installing requirements...
pip install --no-cache-dir -r requirements.txt

:: Create a logs folder
echo Creating logs folder...
mkdir logs

:: --- Create the Startup Shortcut ---

:: Define the path to the user's startup folder
set "startup_folder=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

:: Define the shortcut name
set "shortcut_name=js8-mqtt-bridge.lnk"

:: Find the python executable from the virtual environment
set "venv_python_exe=%project_dir%\venv\Scripts\pythonw.exe"

:: Create the VBScript to make the shortcut
echo Set oShell = WScript.CreateObject("WScript.Shell") > create_shortcut.vbs
echo Set oShortcut = oShell.CreateShortcut("%startup_folder%\%shortcut_name%") >> create_shortcut.vbs
echo oShortcut.TargetPath = "%venv_python_exe%" >> create_shortcut.vbs
echo oShortcut.Arguments = "%project_dir%\%python_script_name%" >> create_shortcut.vbs
echo oShortcut.WorkingDirectory = "%project_dir%" >> create_shortcut.vbs
echo oShortcut.Save >> create_shortcut.vbs

cscript //nologo create_shortcut.vbs
del create_shortcut.vbs

echo.
echo Done. The JS8-MQTT Bridge will now start on user login.
pause


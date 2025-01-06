@echo off
setlocal EnableDelayedExpansion

REM Load environment variables from .env
for /f "tokens=1,* delims==" %%a in (.env) do (
    set %%a=%%b
)

cd /d "%INSTALL_PATH%"
echo Starting TTS Service Setup... >> "%INSTALL_PATH%\service.log" 2>&1

REM Check if Python is installed
python --version >> "%INSTALL_PATH%\service.log" 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH >> "%INSTALL_PATH%\service.log" 2>&1
    exit /b 1
)

REM Check if venv exists, create if it doesn't
if not exist "venv" (
    echo Creating virtual environment... >> "%INSTALL_PATH%\service.log" 2>&1
    python -m venv venv >> "%INSTALL_PATH%\service.log" 2>&1
)

REM Activate virtual environment
call venv\Scripts\activate.bat >> "%INSTALL_PATH%\service.log" 2>&1

REM Upgrade pip
python -m pip install --upgrade pip >> "%INSTALL_PATH%\service.log" 2>&1

REM Install requirements
echo Installing requirements... >> "%INSTALL_PATH%\service.log" 2>&1
pip install -r requirements.txt >> "%INSTALL_PATH%\service.log" 2>&1

REM Run the service
echo Starting TTS service... >> "%INSTALL_PATH%\service.log" 2>&1
pythonw xtts2.py >> "%INSTALL_PATH%\service.log" 2>&1

REM Log any errors
if errorlevel 1 (
    echo Service failed to start with error code %errorlevel% >> "%INSTALL_PATH%\service.log" 2>&1
)

REM Deactivate venv (this line won't be reached while service is running)
deactivate

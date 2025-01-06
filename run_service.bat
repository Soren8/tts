@echo off
setlocal EnableDelayedExpansion

REM Load environment variables from .env
for /f "tokens=1,* delims==" %%a in (.env) do (
    set %%a=%%b
)

cd /d "%INSTALL_PATH%"
echo Starting TTS Service Setup...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if venv exists, create if it doesn't
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Upgrade pip
python -m pip install --upgrade pip

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt

REM Run the service
echo Starting TTS service...
pythonw xtts2.py

REM Keep window open if there's an error
if errorlevel 1 pause

REM Deactivate venv (this line won't be reached while service is running)
deactivate

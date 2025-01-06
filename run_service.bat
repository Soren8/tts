@echo off
setlocal EnableDelayedExpansion

REM Check for admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script requires administrator privileges.
    echo Please run as administrator.
    pause
    exit /b 1
)

REM Load environment variables from .env
for /f "tokens=1,* delims==" %%a in (.env) do (
    set %%a=%%b
)

cd /d "%INSTALL_PATH%"

REM Check for existing pythonw process running xtts2.py and kill it
echo Checking for existing TTS service...
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%xtts2.py%%' and name like '%%pythonw.exe%%'" get processid ^| findstr /r "[0-9]"') do (
    echo Killing existing TTS service PID: %%a
    taskkill /F /PID %%a
    REM Wait for process to terminate
    :waitloop1
    tasklist | find "%%a" >nul
    if not errorlevel 1 (
        timeout /t 1 /nobreak >nul
        goto :waitloop1
    )
)

REM Wait and retry for service.log to become available
:waitforlog
if exist "%INSTALL_PATH%\service.log" (
    2>nul (
        >>"%INSTALL_PATH%\service.log" echo test
    ) && (
        goto :logready
    ) || (
        timeout /t 1 /nobreak >nul
        goto :waitforlog
    )
)
:logready

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

REM Start the service without waiting
start /B pythonw xtts2.py

REM Log any errors
if errorlevel 1 (
    echo Service failed to start with error code %errorlevel% >> "%INSTALL_PATH%\service.log" 2>&1
)

REM No need to deactivate since we're using start /B
endlocal

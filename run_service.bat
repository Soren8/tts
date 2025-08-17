
@echo off
:: Check for administrator privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Running with administrator privileges
) else (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb runAs"
    exit /b
)

:: Change to script directory
cd /d "%~dp0"

:: Run the PowerShell script in the background without a window
start /B powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0run_service.ps1"

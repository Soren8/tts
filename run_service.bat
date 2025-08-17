
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

:: Run the PowerShell script
powershell.exe -ExecutionPolicy Bypass -File "%~dp0run_service.ps1"
set powershellExitCode=%errorlevel%

:: Check if PowerShell script succeeded
if %powershellExitCode% neq 0 (
    echo Error: PowerShell script failed with exit code %powershellExitCode%
    pause
    exit /b %powershellExitCode%
)

:: Pause to see output (optional)
pause

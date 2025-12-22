@echo off
setlocal

where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo uv is not installed. Please install it first: https://docs.astral.sh/uv/getting-started/installation/
    exit /b 1
)

set "SERVICE_SCRIPT=%~1"
if "%SERVICE_SCRIPT%"=="" set "SERVICE_SCRIPT=kokoro_tts.py"

if not exist "%SERVICE_SCRIPT%" (
    echo Error: Service script "%SERVICE_SCRIPT%" not found.
    echo Usage: run_service.bat [script_name.py]
    exit /b 1
)

echo Starting TTS service: %SERVICE_SCRIPT% using uv...

set UV_HTTP_TIMEOUT=600

uv run "%SERVICE_SCRIPT%"

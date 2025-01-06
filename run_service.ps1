#Requires -RunAsAdministrator

# Load environment variables
Get-Content .env | ForEach-Object {
    $name, $value = $_ -split '=', 2
    if ($name -and $value) {
        Set-Item -Path Env:$name -Value $value
    }
}

# Set working directory
Set-Location -Path $env:INSTALL_PATH

# Initialize log file
$logFile = Join-Path $env:INSTALL_PATH "service.log"

# Function to write to log
function Write-Log {
    param([string]$message)
    Add-Content -Path $logFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
}

# Check for existing TTS service
Write-Log "Checking for existing TTS service..."
$processes = Get-Process pythonw -ErrorAction SilentlyContinue | 
    Where-Object { $_.MainWindowTitle -match "xtts2.py" }

if ($processes) {
    foreach ($process in $processes) {
        Write-Log "Stopping existing TTS service PID: $($process.Id)"
        Stop-Process -Id $process.Id -Force
        # Wait for process to terminate
        while (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
            Start-Sleep -Seconds 1
        }
    }
}

# Check Python installation
try {
    $pythonVersion = & python --version 2>&1
    Write-Log "Python version: $pythonVersion"
}
catch {
    Write-Log "Python is not installed or not in PATH"
    exit 1
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Log "Creating virtual environment..."
    & python -m venv venv 2>&1 | Tee-Object -FilePath $logFile -Append
}

# Activate virtual environment
$activateScript = Join-Path $env:INSTALL_PATH "venv\Scripts\Activate.ps1"
. $activateScript

# Upgrade pip
Write-Log "Upgrading pip..."
& python -m pip install --upgrade pip 2>&1 | Tee-Object -FilePath $logFile -Append

# Install requirements
Write-Log "Installing requirements..."
& pip install -r requirements.txt 2>&1 | Tee-Object -FilePath $logFile -Append

# Start the service
Write-Log "Starting TTS service..."
Start-Process pythonw -ArgumentList "xtts2.py" -NoNewWindow

Write-Log "TTS service started successfully"

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

# Function to write to log safely with file locking
function Write-Log-Safe {
    param([string]$message)
    try {
        $logFile = Join-Path $env:INSTALL_PATH "service.log"
        $stream = [System.IO.File]::Open($logFile, 'Append', 'Write', 'Read')
        $writer = New-Object System.IO.StreamWriter($stream)
        $writer.WriteLine("$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message")
        $writer.Close()
        $stream.Close()
    }
    catch {
        # If we can't write to the log, at least show the message in the console
        Write-Host $message
    }
}

# Stop any existing services
Write-Log-Safe "Stopping any existing TTS services..."
& "$PSScriptRoot\kill_service.ps1"

# Check Python installation
try {
    $pythonVersion = & python --version 2>&1
    Write-Log-Safe "Python version: $pythonVersion"
}
catch {
    Write-Log-Safe "Python is not installed or not in PATH"
    exit 1
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Log-Safe "Creating virtual environment..."
    & python -m venv venv 2>&1 | ForEach-Object { Write-Log-Safe $_ }
}

# Activate virtual environment
$activateScript = Join-Path $env:INSTALL_PATH "venv\Scripts\Activate.ps1"
. $activateScript

# Upgrade pip
Write-Log-Safe "Upgrading pip..."
& python -m pip install --upgrade pip 2>&1 | ForEach-Object { Write-Log-Safe $_ }

# Install requirements
Write-Log-Safe "Installing requirements..."
& pip install -r requirements.txt 2>&1 | ForEach-Object { Write-Log-Safe $_ }

# Start the service
Write-Log-Safe "Starting TTS service..."
Start-Process pythonw -ArgumentList "xtts2.py" -NoNewWindow

Write-Log-Safe "TTS service started successfully"

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

# Start the service
Write-Log-Safe "Starting TTS service..."
try {
    # Start the service in a hidden window and don't wait
    $process = Start-Process python -ArgumentList "kokoro_tts.py" -WindowStyle Hidden -PassThru
    
    Write-Log-Safe "TTS service started (PID: $($process.Id))"
} catch {
    Write-Log-Safe "Failed to start TTS service: $_"
    exit 1
}

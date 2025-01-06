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

# Check for existing TTS service
Write-Log-Safe "Checking for existing TTS service..."
$processes = Get-Process pythonw -ErrorAction SilentlyContinue | 
    Where-Object { 
        $_.ProcessName -eq "pythonw" -and 
        $_.Modules.FileName -match "xtts2.py"
    }

if ($processes) {
    foreach ($process in $processes) {
        Write-Log-Safe "Stopping existing TTS service PID: $($process.Id)"
        Stop-Process -Id $process.Id -Force
        # Wait for process to terminate
        while (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
            Start-Sleep -Seconds 1
        }
    }
    Write-Log-Safe "All TTS services stopped successfully"
} else {
    Write-Log-Safe "No running TTS services found"
}

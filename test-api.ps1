# Define the API base URL
$baseUrl = "http://localhost:5000"

# Test the /api/status endpoint
Write-Host "Testing /api/status endpoint..."
$statusResponse = Invoke-RestMethod -Uri "$baseUrl/api/status" -Method Get
Write-Host "Status Response:"
$statusResponse | ConvertTo-Json -Depth 3

# Test the /api/tts endpoint
Write-Host "`nTesting /api/tts endpoint..."
$ttsPayload = @{
    text = "Hello, this is a test of the text-to-speech API. How are you today?"
    voice_file = "voices/default.wav"
}
$ttsResponse = Invoke-RestMethod -Uri "$baseUrl/api/tts" -Method Post -Body ($ttsPayload | ConvertTo-Json) -ContentType "application/json"
Write-Host "TTS Response:"
$ttsResponse | ConvertTo-Json -Depth 3

# Test the /api/audio/<filename> endpoint
if ($ttsResponse.file) {
    Write-Host "`nTesting /api/audio/<filename> endpoint..."
    $audioUrl = "$baseUrl/api/audio/$($ttsResponse.file)"
    $audioResponse = Invoke-WebRequest -Uri $audioUrl -Method Get -OutFile "output.wav"
    Write-Host "Audio file saved as 'output.wav'"
} else {
    Write-Host "`nError: No audio file was generated."
}

Write-Host "`nAPI testing complete."

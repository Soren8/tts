import requests
import json
import sys
import sounddevice as sd
import numpy as np
import wave
import io

# Define the API base URL
base_url = "http://localhost:5000"

def test_api():
    # Test the /api/status endpoint
    print("Testing /api/status endpoint...")
    try:
        status_response = requests.get(f"{base_url}/api/status")
        status_response.raise_for_status()  # Raise an exception for bad status codes
        print("Status Response:")
        print(json.dumps(status_response.json(), indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Error testing status endpoint: {e}")
        sys.exit(1)

    # Test the /api/tts endpoint
    print("\nTesting /api/tts endpoint...")
    tts_payload = {
        "text": "Hello, this is a test sentence.",
        "voice_file": "voices/default.wav"
    }
    try:
        tts_response = requests.post(
            f"{base_url}/api/tts",
            json=tts_payload
        )
        tts_response.raise_for_status()
        print("TTS Response:")
        print(json.dumps(tts_response.json(), indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Error testing TTS endpoint: {e}")
        sys.exit(1)

    # Test the /api/audio/<filename> endpoint
    response_data = tts_response.json()
    if 'file' in response_data:
        print("\nTesting /api/audio/<filename> endpoint...")
        try:
            audio_response = requests.get(f"{base_url}/api/audio/{response_data['file']}")
            audio_response.raise_for_status()
            
            # Play the audio directly
            wav_file = io.BytesIO(audio_response.content)
            with wave.open(wav_file, 'rb') as wf:
                # Get audio parameters
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                
                # Read the audio data
                audio_data = wf.readframes(wf.getnframes())
                
                # Convert to numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # Play the audio
                print("Playing audio...")
                sd.play(audio_array, sample_rate)
                sd.wait()  # Wait until audio finishes playing
        except requests.exceptions.RequestException as e:
            print(f"Error downloading audio file: {e}")
            sys.exit(1)
    else:
        print("\nError: No audio file was generated.")
        sys.exit(1)

    print("\nAPI testing complete.")

if __name__ == "__main__":
    test_api()

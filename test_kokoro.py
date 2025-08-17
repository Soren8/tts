import requests
import os

def test_kokoro_tts():
    """Test the Kokoro TTS service by sending a text request and saving the audio response."""
    url = "http://localhost:5001/api/tts"
    data = {"text": "Hello, this is a test of the Kokoro TTS service running on port 5001."}
    
    print("Sending TTS request to http://localhost:5001/api/tts...")
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        # Save the audio file
        output_dir = os.path.join(os.getcwd(), 'outputs')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'kokoro_test.wav')
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"\nAudio successfully generated and saved to {output_path}")
        print(f"File size: {os.path.getsize(output_path)/1024:.2f} KB")
        print("\nYou can play this file with any audio player to hear the result.")
    else:
        print(f"\nError: HTTP {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    print("="*50)
    print("KOKORO TTS SERVICE TEST SCRIPT")
    print("="*50)
    test_kokoro_tts()
    print("="*50)

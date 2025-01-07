import requests
import json
import sys
import argparse

# Define the API base URL
base_url = "http://localhost:5000"

def test_api(input_text, output_filename):
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

    # Read the input text file
    try:
        with open(input_text, 'r') as file:
            text_content = file.read()
    except Exception as e:
        print(f"Error reading input file: {e}")
        sys.exit(1)

    # Test the /api/tts endpoint with the file content
    print("\nTesting /api/tts endpoint...")
    tts_payload = {
        "text": text_content,
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
            
            if output_filename:
                # Save the audio to the output file
                with open(output_filename, 'wb') as f:
                    f.write(audio_response.content)
                print(f"Audio saved to {output_filename}")
            else:
                print("Audio generated successfully (not saved to file)")
        except requests.exceptions.RequestException as e:
            print(f"Error downloading audio file: {e}")
            sys.exit(1)
    else:
        print("\nError: No audio file was generated.")
        sys.exit(1)

    print("\nAPI testing complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert text file to speech using TTS API')
    parser.add_argument('input_file', help='Path to the input text file')
    parser.add_argument('output_file', nargs='?', help='Path to save the output audio file (optional)')
    args = parser.parse_args()
    
    test_api(args.input_file, args.output_file)

import requests
import json
import sys
import argparse
import os

# Define the API base URL
base_url = "http://localhost:5000"

# Check for text directory
text_dir = os.path.join(os.getcwd(), 'text')
if not os.path.exists(text_dir):
    print(f"Error: 'text' directory does not exist at '{text_dir}'")
    print("Please create a 'text' directory in your project root and place your text files there.")
    sys.exit(1)

def test_api(input_text, output_filename):
    # Test the /api/status endpoint
    print("Testing /api/status endpoint...")
    try:
        status_response = requests.get(f"{base_url}/api/status", timeout=10)
        status_response.raise_for_status()  # Raise an exception for bad status codes
        print("Status Response:")
        print(json.dumps(status_response.json(), indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Error testing status endpoint: {e}")
        sys.exit(1)

    # Read the input text file
    input_path = os.path.abspath(os.path.join(text_dir, input_text))
    
    # Verify input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file does not exist at '{input_path}'")
        print("Current working directory:", os.getcwd())
        print("Please ensure the file exists in the text directory and the path is correct.")
        sys.exit(1)
        
    try:
        with open(input_path, 'r', encoding='utf-8') as file:
            text_content = file.read()
    except Exception as e:
        print(f"Error reading input file '{input_path}': {e}")
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
            json=tts_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        tts_response.raise_for_status()
        print("TTS Response: Received audio data (binary)")
    except requests.exceptions.RequestException as e:
        print(f"Error testing TTS endpoint: {e}")
        print("Response content:", tts_response.content)
        sys.exit(1)

    # Save the audio data directly from the TTS response
    if output_filename:
        output_path = os.path.abspath(os.path.join(os.getcwd(), output_filename))
        
        # Create output directory if needed
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                print(f"Error creating output directory '{output_dir}': {e}")
                sys.exit(1)
                
        try:
            with open(output_path, 'wb') as f:
                f.write(tts_response.content)
            print(f"Audio saved to {output_path}")
        except Exception as e:
            print(f"Error saving output file '{output_path}': {e}")
            sys.exit(1)
    else:
        print("Audio generated successfully (not saved to file)")

    print("\nAPI testing complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert text file to speech using TTS API')
    parser.add_argument('input_file', help='Path to the input text file')
    parser.add_argument('output_file', nargs='?', help='Path to save the output audio file (optional)')
    args = parser.parse_args()
    
    test_api(args.input_file, args.output_file)

# /// script
# dependencies = [
#   "requests",
# ]
# ///

import requests
import os

BASE_URL = "http://localhost:5000/api"
OUTPUT_DIR = "voice_samples"

# Hardcoded voices based on Kokoro-82M defaults
VOICES = [
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_michael",
    "bf_emma", "bf_isabella",
    "bm_george", "bm_lewis"
]

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    test_text = "Hello! This is a test of my voice using Kokoro T T S."
    
    for voice in VOICES:
        print(f"Generating sample for voice: {voice}...", end="", flush=True)
        try:
            payload = {
                "text": test_text,
                "voice": voice,
                "speed": 1.0
            }
            # Use the correct endpoint /api/tts
            res = requests.post(f"{BASE_URL}/tts", json=payload)
            res.raise_for_status()
            
            output_path = os.path.join(OUTPUT_DIR, f"{voice}.wav")
            with open(output_path, "wb") as f:
                f.write(res.content)
            print(" Done.")
        except Exception as e:
            print(f" Failed: {e}")

if __name__ == "__main__":
    main()

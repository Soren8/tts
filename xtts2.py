import torch
from TTS.api import TTS
import sounddevice as sd
import numpy as np
import soundfile as sf

# Get device
device = "cuda" if torch.cuda.is_available() else "cpu"

# List available 🐸TTS models
print(TTS().list_models())

# Init TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

while True:
    #text = input("Enter the text you want to convert to speech (or 'quit' to exit): ")
    filename = input("Enter the filename containing the text to convert to speech (or 'quit' to exit): ")
    
    if filename.lower() == 'quit':
        break
    
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            text = file.read()
        
        print(f"Text read from {filename}:")
        print(text)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found. Please try again.")

    # Run TTS
    wav = tts.tts(text, speaker_wav="jenny.wav", language="en")
    audio = np.array(wav)
    print("Playing audio...")
    sd.play(audio, samplerate=tts.synthesizer.output_sample_rate)
    sd.wait()  # Wait until the audio is finished playing

    # Optionally, save the audio file
    sf.write("output.wav", audio, tts.synthesizer.output_sample_rate)
    print("Audio file 'output.wav' has been generated.")
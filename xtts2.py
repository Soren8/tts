import torch
from TTS.api import TTS
import sounddevice as sd
import numpy as np
import re
import threading
import queue

# Get device
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Init TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# Set up audio stream
sample_rate = tts.synthesizer.output_sample_rate

def split_into_sentences(text):
    # Simple sentence splitting. You might want to use a more sophisticated method.
    return re.split('(?<=[.!?]) +', text)

def tts_generator(sentences, audio_queue):
    for sentence in sentences:
        if sentence.strip():  # Skip empty sentences
            wav = tts.tts(sentence, speaker_wav="jenny.wav", language="en")
            audio = np.array(wav)
            audio_queue.put(audio)
    audio_queue.put(None)  # Signal that generation is complete

def audio_player(audio_queue):
    while True:
        audio = audio_queue.get()
        if audio is None:
            break
        sd.play(audio, samplerate=sample_rate)
        sd.wait()  # Wait until this sentence's audio is finished playing

while True:
    filename = input("Enter the filename containing the text to convert to speech (or 'quit' to exit): ")
    
    if filename.lower() == 'quit':
        break
    
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            text = file.read()
        
        print(f"Text read from {filename}:")
        print(text)

        sentences = split_into_sentences(text)

        print("Generating and playing audio...")

        audio_queue = queue.Queue()

        tts_thread = threading.Thread(target=tts_generator, args=(sentences, audio_queue))
        audio_thread = threading.Thread(target=audio_player, args=(audio_queue,))

        tts_thread.start()
        audio_thread.start()

        tts_thread.join()
        audio_thread.join()

        print("Audio playback complete.")

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found. Please try again.")
    except Exception as e:
        print(f"An error occurred: {e}")

print("Program ended.")

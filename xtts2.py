import torch
from TTS.api import TTS
import sounddevice as sd
import numpy as np
import re
import threading
import queue
import wave
import os

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

def tts_generator(sentences, audio_queue, audio_segments, voice_file):
    for sentence in sentences:
        if sentence.strip():  # Skip empty sentences
            wav = tts.tts(sentence, speaker_wav=voice_file, language="en")
            audio = np.array(wav)
            audio_queue.put(audio)
            audio_segments.append(audio)  # Collect audio for saving
    audio_queue.put(None)  # Signal that generation is complete

def audio_player(audio_queue):
    while True:
        audio = audio_queue.get()
        if audio is None:
            break
        sd.play(audio, samplerate=sample_rate)
        sd.wait()  # Wait until this sentence's audio is finished playing

def save_audio(audio_segments, filename):
    # Concatenate all audio segments
    if not audio_segments:
        print("No audio segments to save.")
        return
    concatenated_audio = np.concatenate(audio_segments)

    # Normalize audio to prevent clipping
    max_val = np.max(np.abs(concatenated_audio))
    if max_val > 0:
        concatenated_audio = concatenated_audio / max_val

    # Convert to 16-bit PCM
    concatenated_audio = (concatenated_audio * 32767).astype(np.int16)

    # Write to WAV file
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 2 bytes per sample
        wf.setframerate(sample_rate)
        wf.writeframes(concatenated_audio.tobytes())
    print(f"All audio saved to {filename}")

while True:
    filename = input("Enter the filename containing the text to convert to speech (or 'quit' to exit): ")
    
    if filename.lower() == 'quit':
        break
    if not os.path.isabs(filename) and not filename.startswith('text/'):
        filename = f"text/{filename}"
    
    voice_file = input("Enter the voice file to use (or press Enter for default 'voices/chris.wav'): ")
    if not voice_file:
        voice_file = "voices/chris.wav"
    elif not os.path.isabs(voice_file) and not voice_file.startswith('voices/'):
        voice_file = f"voices/{voice_file}"
    
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            text = file.read()
        
        print(f"Text read from {filename}:")
        print(text)

        sentences = split_into_sentences(text)

        print("Generating and playing audio...")

        audio_queue = queue.Queue()
        audio_segments = []  # List to collect audio segments

        tts_thread = threading.Thread(target=tts_generator, args=(sentences, audio_queue, audio_segments, voice_file))
        audio_thread = threading.Thread(target=audio_player, args=(audio_queue,))

        tts_thread.start()
        audio_thread.start()

        tts_thread.join()
        audio_thread.join()

        print("Audio playback complete.")

        # Save all audio
        outfilename = f"outputs/{os.path.splitext(os.path.basename(filename))[0]}.wav"
        save_audio(audio_segments, filename=outfilename)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found. Please try again.")
    except Exception as e:
        print(f"An error occurred: {e}")

print("Program ended.")

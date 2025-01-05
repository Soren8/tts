import torch
from TTS.api import TTS
from TTS.utils.manage import ModelManager

# Pre-download the model and accept the license
ModelManager().download_model("tts_models/multilingual/multi-dataset/xtts_v2")
import numpy as np
import re
import wave
import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Get device
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Init TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# Set up audio stream
sample_rate = tts.synthesizer.output_sample_rate

def split_into_sentences(text):
    # Simple sentence splitting
    return re.split('(?<=[.!?]) +', text)

def tts_generator(sentences, audio_segments, voice_file):
    for sentence in sentences:
        if sentence.strip():  # Skip empty sentences
            wav = tts.tts(sentence, speaker_wav=voice_file, language="en")
            audio = np.array(wav)
            audio_segments.append(audio)  # Collect audio for saving

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

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    data = request.json
    text = data.get('text')
    voice_file = data.get('voice_file', 'voices/default.wav')

    if not text:
        return jsonify({"error": "Text is required"}), 400

    sentences = split_into_sentences(text)
    audio_segments = []  # List to collect audio segments

    # Generate audio without playback
    tts_generator(sentences, audio_segments, voice_file)

    # Save the audio to a file
    output_filename = f"output_{len(os.listdir('outputs')) + 1}.wav"
    save_audio(audio_segments, os.path.join('outputs', output_filename))

    return jsonify({"message": "Audio generated successfully", "file": output_filename}), 200

@app.route('/api/audio/<filename>', methods=['GET'])
def get_audio(filename):
    file_path = os.path.join('outputs', filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, mimetype='audio/wav')

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({"status": "running", "device": device}), 200

if __name__ == '__main__':
    # Create necessary directories if they don't exist
    os.makedirs('outputs', exist_ok=True)
    os.makedirs('voices', exist_ok=True)
    os.makedirs('text', exist_ok=True)

    # Run the Flask app
    app.run(host='0.0.0.0', port=5000)

import torch
from TTS.api import TTS
from TTS.utils.manage import ModelManager
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

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

# Set up logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'service.log')
try:
    logging.basicConfig(
        handlers=[RotatingFileHandler(log_file, maxBytes=10485760, backupCount=5, delay=True)],
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)
except PermissionError:
    # Fallback to a unique log file if the main one is locked
    import tempfile
    temp_dir = tempfile.gettempdir()
    fallback_log = os.path.join(temp_dir, f'tts_service_{os.getpid()}.log')
    logging.basicConfig(
        handlers=[RotatingFileHandler(fallback_log, maxBytes=10485760, backupCount=5)],
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not write to {log_file}, using fallback log file: {fallback_log}")

@app.after_request
def after_request(response):
    logger.info(f'{request.remote_addr} - "{request.method} {request.path}" {response.status_code}')
    return response

# Get device and print diagnostic information
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA device count: {torch.cuda.device_count()}")
    print(f"CUDA device name: {torch.cuda.get_device_name(0)}")

# Init TTS with explicit device handling
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
if torch.cuda.is_available():
    tts = tts.to("cuda")
else:
    print("WARNING: CUDA not available, using CPU")
    tts = tts.to("cpu")

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
    logger.info(f"Received TTS request from {request.remote_addr}")
    data = request.json
    text = data.get('text')
    voice_file = data.get('voice_file', 'voices/default.wav')

    if not text:
        logger.error("No text provided in request")
        return jsonify({"error": "Text is required"}), 400

    sentences = split_into_sentences(text)
    audio_segments = []

    try:
        tts_generator(sentences, audio_segments, voice_file)
        output_filename = f"output_{len(os.listdir('outputs')) + 1}.wav"
        save_audio(audio_segments, os.path.join('outputs', output_filename))
        logger.info(f"Successfully generated audio: {output_filename}")
        return jsonify({"message": "Audio generated successfully", "file": output_filename}), 200
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/audio/<filename>', methods=['GET'])
def get_audio(filename):
    logger.info(f"Audio file request for {filename} from {request.remote_addr}")
    file_path = os.path.join('outputs', filename)
    if not os.path.exists(file_path):
        logger.error(f"File not found: {filename}")
        return jsonify({"error": "File not found"}), 404
    logger.info(f"Serving audio file: {filename}")
    return send_file(file_path, mimetype='audio/wav')

@app.route('/api/status', methods=['GET'])
def status():
    logger.info(f"Status check from {request.remote_addr}")
    return jsonify({"status": "running", "device": device}), 200

if __name__ == '__main__':
    # Load environment variables
    load_dotenv()
    
    # Create necessary directories if they don't exist
    os.makedirs('outputs', exist_ok=True)
    os.makedirs('voices', exist_ok=True)
    os.makedirs('text', exist_ok=True)

    # Get port from environment variable, default to 5000 if not set
    port = int(os.getenv('PORT', 5000))

    logger.info(f"Starting TTS service on port {port}")
    logger.info(f"Using device: {device}")
    
    # Run the Flask app 
    app.run(host='0.0.0.0', port=port)

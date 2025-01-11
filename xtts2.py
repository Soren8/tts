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
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

try:
    # Create rotating file handler
    file_handler = RotatingFileHandler(log_file, maxBytes=10485760, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
except PermissionError:
    # Fallback to a unique log file if the main one is locked
    import tempfile
    temp_dir = tempfile.gettempdir()
    fallback_log = os.path.join(temp_dir, f'tts_service_{os.getpid()}.log')
    file_handler = RotatingFileHandler(fallback_log, maxBytes=10485760, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.warning(f"Could not write to {log_file}, using fallback log file: {fallback_log}")

# Remove any existing handlers from the root logger
logging.getLogger().handlers = []

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

def preprocess_text(text):
    """Clean and prepare text for TTS processing"""
    # Remove newlines and extra spaces
    text = ' '.join(text.split())
    # Add any other preprocessing steps here if needed
    return text.strip()

def split_into_sentences(text):
    # Simple sentence splitting
    return re.split('(?<=[.!?]) +', text)

def tts_generator(sentences, audio_segments, voice_file):
    for sentence in sentences:
        if sentence.strip():  # Skip empty sentences
            wav = tts.tts(sentence, speaker_wav=voice_file, language="en")
            audio = np.array(wav)
            audio_segments.append(audio)  # Collect audio for saving


@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    logger.info(f"Received TTS request from {request.remote_addr}")
    data = request.json
    text = data.get('text')
    voice_file = data.get('voice_file', 'voices/default.wav')

    if not text:
        logger.error("No text provided in request")
        return jsonify({"error": "Text is required"}), 400

    # Preprocess the text
    text = preprocess_text(text)
    sentences = split_into_sentences(text)
    audio_segments = []

    try:
        tts_generator(sentences, audio_segments, voice_file)
        
        # Concatenate audio segments
        concatenated_audio = np.concatenate(audio_segments)
        
        # Normalize audio
        max_val = np.max(np.abs(concatenated_audio))
        if max_val > 0:
            concatenated_audio = concatenated_audio / max_val
        
        # Convert to 16-bit PCM
        concatenated_audio = (concatenated_audio * 32767).astype(np.int16)
        
        # Create in-memory WAV file
        import io
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(concatenated_audio.tobytes())
        
        wav_io.seek(0)
        logger.info("Successfully generated audio")
        return send_file(wav_io, mimetype='audio/wav')
        
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/status', methods=['GET'])
def status():
    logger.info(f"Status check from {request.remote_addr}")
    return jsonify({"status": "running", "device": device}), 200

if __name__ == '__main__':
    # Load environment variables
    load_dotenv()
    
    # Create necessary directories if they don't exist
    os.makedirs('voices', exist_ok=True)
    os.makedirs('text', exist_ok=True)

    # Get port from environment variable, default to 5000 if not set
    port = int(os.getenv('PORT', 5000))

    logger.info(f"Starting TTS service on port {port}")
    logger.info(f"Using device: {device}")
    
    # Run the Flask app 
    app.run(host='0.0.0.0', port=port)

import os
import sys
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import io

# Path to your virtualenv (using standard 'venv' name)
VENV_PATH = os.path.join(os.path.dirname(__file__), 'venv')
VENV_ACTIVATE = os.path.join(VENV_PATH, 'Scripts', 'activate.bat')
VENV_PYTHON = os.path.join(VENV_PATH, 'Scripts', 'python.exe')

def ensure_venv():
    # Check if we're in the virtualenv
    if os.path.normpath(sys.prefix) != os.path.normpath(VENV_PATH):
        # Create venv if it doesn't exist
        if not os.path.exists(VENV_PYTHON):
            print("Creating virtualenv...")
            subprocess.run([sys.executable, '-m', 'venv', VENV_PATH], check=True)
        # Re-run the script in the virtualenv
        print("Activating virtualenv and rerunning...")
        subprocess.run(f'"{VENV_ACTIVATE}" && "{VENV_PYTHON}" "{__file__}" {" ".join(sys.argv[1:])}', shell=True)
        sys.exit()
    # List of required packages with versions where needed
    requirements = [
        'torch==2.8.0',
        'kokoro',
        'misaki[en]',
        'soundfile',
        'numpy',
        'flask',
        'flask-cors'
    ]
    for pkg in requirements:
        try:
            __import__(pkg.split('==')[0].split('[')[0])  # Check if importable
        except ImportError as e:
            print(f"Installing {pkg}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], check=True)

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

# Ensure virtualenv is active
ensure_venv()

# Original script imports (now safe after installs)
import numpy as np
from flask import Flask, request, jsonify, send_file, Response
import torch
import soundfile as sf
from kokoro import KPipeline

# Remove any existing handlers from the root logger
logging.getLogger().handlers = []

# Device detection
device = "cuda" if torch.cuda.is_available() else "cpu"

# Initialize Flask app
app = Flask(__name__)

# Global pipeline instance
pipeline = None

def get_pipeline():
    global pipeline
    if pipeline is None:
        pipeline = KPipeline(lang_code='a')  # American English
    return pipeline

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    logger.info(f"Received TTS request from {request.remote_addr}")
    data = request.json
    text = data.get('text')
    
    if not text:
        logger.error("No text provided in request")
        return jsonify({"error": "Text is required"}), 400

    try:
        # Generate audio
        pipeline = get_pipeline()
        voice = 'af_heart'
        generator = pipeline(text, voice=voice, speed=1.0)
        
        # Collect all audio chunks
        audio_chunks = []
        for i, (gs, ps, audio) in enumerate(generator):
            audio_chunks.append(audio)
            logger.info(f"Generated audio chunk {i}")
        
        # Concatenate audio chunks
        if audio_chunks:
            concatenated_audio = np.concatenate(audio_chunks)
        else:
            logger.error("No audio generated")
            return jsonify({"error": "No audio generated"}), 500
        
        # Create in-memory WAV file
        wav_io = io.BytesIO()
        sf.write(wav_io, concatenated_audio, 24000, format='WAV')
        wav_io.seek(0)
        
        logger.info("Successfully generated audio")
        return send_file(wav_io, mimetype='audio/wav')
        
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/tts/stream', methods=['POST'])
def text_to_speech_stream():
    logger.info(f"Received streaming TTS request from {request.remote_addr}")
    data = request.json
    text = data.get('text')
    
    if not text:
        logger.error("No text provided in request")
        return jsonify({"error": "Text is required"}), 400

    def generate(text_to_process):
        try:
            pipeline = get_pipeline()
            voice = 'af_heart'
            generator = pipeline(text_to_process, voice=voice, speed=1.0)
            
            for i, (gs, ps, audio) in enumerate(generator):
                # Create in-memory WAV file for this chunk
                wav_io = io.BytesIO()
                sf.write(wav_io, audio, 24000, format='WAV')
                wav_io.seek(0)
                
                yield wav_io.getvalue()
                logger.info(f"Streamed audio chunk {i}")
                
        except Exception as e:
            logger.error(f"Error generating audio stream: {str(e)}")
            # We can't return an error in a stream, so just log it
            return

    return Response(generate(text), mimetype='audio/wav')

@app.route('/api/status', methods=['GET'])
def status():
    logger.info(f"Status check from {request.remote_addr}")
    return jsonify({"status": "running", "device": device}), 200

if __name__ == "__main__":
    # Create necessary directories if they don't exist
    os.makedirs('outputs', exist_ok=True)
    
    # Get port from environment variable, default to 5000 if not set
    port = int(os.getenv('PORT', 5000))
    
    logger.info(f"Starting Kokoro TTS service on port {port}")
    
    # Run the Flask app 
    app.run(host='0.0.0.0', port=port)

# /// script
# dependencies = [
#   "flask>=2.3.2",
#   "flask-cors>=4.0.0",
#   "numpy",
#   "scipy",
#   "soundfile",
#   "kokoro",
#   "misaki[en]",
#   "torch",
#   "hf-xet",
#   "pip",
# ]
# [[tool.uv.index]]
# name = "pytorch-cu128"
# url = "https://download.pytorch.org/whl/cu128"
# explicit = true
# [tool.uv.sources]
# torch = { index = "pytorch-cu128" }
# ///

import os
import logging
from logging.handlers import RotatingFileHandler
import io
import numpy as np
from flask import Flask, request, jsonify, send_file, Response
import torch
import soundfile as sf
from kokoro import KPipeline

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

# Device detection
device = "cuda" if torch.cuda.is_available() else "cpu"

# Global pipeline instances for different languages
pipelines = {}

def get_pipeline(lang_code='b'):
    global pipelines
    if lang_code not in pipelines:
        logger.info(f"Initializing Kokoro pipeline for lang_code='{lang_code}'")
        pipelines[lang_code] = KPipeline(lang_code=lang_code, device=device)
    return pipelines[lang_code]

# Pre-warm with British English for bf_emma
get_pipeline('b')

# Initialize Flask app
app = Flask(__name__)

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    logger.info(f"Received TTS request from {request.remote_addr}")
    data = request.json
    text = data.get('text')
    voice = data.get('voice', 'bf_emma')
    speed = float(data.get('speed', 1.0))
    
    # Automatically pick lang_code based on voice prefix if not provided
    # bf_* -> 'b', af_* -> 'a', etc.
    default_lang = 'b' if voice.startswith('b') else 'a'
    lang_code = data.get('lang_code', default_lang)
    
    if not text:
        logger.error("No text provided in request")
        return jsonify({"error": "Text is required"}), 400

    try:
        # Generate audio
        p = get_pipeline(lang_code)
        generator = p(text, voice=voice, speed=speed)
        
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
    voice = data.get('voice', 'bf_emma')
    speed = float(data.get('speed', 1.0))
    
    default_lang = 'b' if voice.startswith('b') else 'a'
    lang_code = data.get('lang_code', default_lang)
    
    if not text:
        logger.error("No text provided in request")
        return jsonify({"error": "Text is required"}), 400

    def generate(text_to_process, voice_to_use, speed_to_use, lang):
        try:
            p = get_pipeline(lang)
            generator = p(text_to_process, voice=voice_to_use, speed=speed_to_use)
            
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

    return Response(generate(text, voice, speed, lang_code), mimetype='audio/wav')

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
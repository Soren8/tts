import os
import logging
from pathlib import Path
from fish_speech_lib.inference import FishSpeech
import soundfile as sf
from flask import Flask, request, jsonify, send_file, Response
import io
import numpy as np
import tempfile
import traceback
import torch

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)

# Create .project-root file before importing fish speech library
project_root_file = '.project-root'
if not os.path.exists(project_root_file):
    Path(project_root_file).touch()
    logger.info("Created .project-root file")

# Device detection
device = "cuda" if torch.cuda.is_available() else "cpu"

# Lazily initialized FishSpeech instance
_tts_instance = None

def get_tts():
    global _tts_instance
    if _tts_instance is None:
        logger.info(f"Initializing FishSpeech on device: {device}")
        _tts_instance = FishSpeech(device=device)
    return _tts_instance

def synthesize_bytes(text, ref_audio_path, ref_text, max_new_tokens=1000, chunk_length=1000):
    TARGET_SR = 24000
    tts = get_tts()
    sample_rate, audio_data = tts(
        text=text,
        reference_audio=ref_audio_path,
        reference_audio_text=ref_text,
        max_new_tokens=max_new_tokens,
        chunk_length=chunk_length
    )

    audio = np.asarray(audio_data).astype('float32')
    
    def _resample_audio(aud, orig_sr, target_sr):
        if int(orig_sr) == int(target_sr):
            return aud
        n_samples = aud.shape[0]
        new_len = int(round(n_samples * float(target_sr) / float(orig_sr)))
        if new_len <= 0:
            raise ValueError("Computed new length for resampling is <= 0")
        old_positions = np.linspace(0, n_samples - 1, num=n_samples)
        new_positions = np.linspace(0, n_samples - 1, num=new_len)
        if aud.ndim == 1:
            return np.interp(new_positions, old_positions, aud).astype('float32')
        else:
            channels = aud.shape[1]
            resampled = np.zeros((new_len, channels), dtype='float32')
            for ch in range(channels):
                resampled[:, ch] = np.interp(new_positions, old_positions, aud[:, ch])
            return resampled

    if int(sample_rate) != TARGET_SR:
        try:
            logger.info(f"Resampling audio from {int(sample_rate)} Hz to {TARGET_SR} Hz")
            audio = _resample_audio(audio, int(sample_rate), TARGET_SR)
            sample_rate = TARGET_SR
        except Exception as e:
            logger.warning(f"Resampling failed: {e}")

    wav_io = io.BytesIO()
    sf.write(wav_io, audio, int(sample_rate), format='WAV')
    wav_io.seek(0)
    return wav_io

app = Flask(__name__)

@app.route('/api/tts', methods=['POST'])
def http_tts():
    logger.info(f"Received TTS request from {request.remote_addr}")
    try:
        if request.is_json:
            req = request.get_json()
            text = req.get("text")
            ref_text = req.get("ref_text")
            ref_audio_path = req.get("ref_audio_path")
            max_new_tokens = req.get("max_new_tokens", 1000)
            chunk_length = req.get("chunk_length", 1000)
            uploaded_file = None
        else:
            text = request.form.get("text")
            ref_text = request.form.get("ref_text")
            ref_audio_path = request.form.get("ref_audio_path")
            max_new_tokens = int(request.form.get("max_new_tokens", 1000))
            chunk_length = int(request.form.get("chunk_length", 1000))
            uploaded_file = request.files.get("ref_audio")

        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        ref_text = ref_text or ""
        temp_file_path = None
        default_ref_audio = os.path.join(os.getcwd(), 'voices', 'default.wav')
        
        if uploaded_file:
            tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            uploaded_file.save(tmpf.name)
            temp_file_path = tmpf.name
            ref_audio_to_use = temp_file_path
        elif ref_audio_path and os.path.exists(ref_audio_path):
            ref_audio_to_use = ref_audio_path
        elif os.path.exists(default_ref_audio):
            ref_audio_to_use = default_ref_audio
        else:
            return jsonify({"error": "Reference audio not found"}), 400

        wav_io = synthesize_bytes(text, ref_audio_to_use, ref_text, max_new_tokens=max_new_tokens, chunk_length=chunk_length)

        if temp_file_path:
            try:
                os.remove(temp_file_path)
            except:
                pass

        return send_file(wav_io, mimetype='audio/wav')

    except Exception as e:
        logger.error(f"Error: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({"status": "running", "device": device}), 200

if __name__ == '__main__':
    os.makedirs('outputs', exist_ok=True)
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
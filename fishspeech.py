import os
import sys
import subprocess
import logging
from pathlib import Path

# Virtualenv path inside the current directory (user's git repo)
VENV_PATH = 'fishspeech_venv'
VENV_PYTHON = os.path.join(VENV_PATH, 'bin', 'python') if os.name != 'nt' else os.path.join(VENV_PATH, 'Scripts', 'python.exe')
VENV_ACTIVATE = os.path.join(VENV_PATH, 'bin', 'activate') if os.name != 'nt' else os.path.join(VENV_PATH, 'Scripts', 'activate.bat')

def ensure_venv():
    # Check if we're in the virtualenv
    if os.path.normpath(sys.prefix) != os.path.normpath(os.path.abspath(VENV_PATH)):
        # Create venv if it doesn't exist
        if not os.path.exists(VENV_PYTHON):
            print("Creating virtualenv with system site packages...")
            subprocess.run([sys.executable, '-m', 'venv', VENV_PATH, '--system-site-packages'], check=True)
        # Re-run the script in the virtualenv
        print("Activating virtualenv and rerunning...")
        if os.name == 'nt':
            cmd = f'"{VENV_ACTIVATE}" && "{VENV_PYTHON}" "{__file__}" {" ".join(sys.argv[1:])}'
        else:
            cmd = f'source "{VENV_ACTIVATE}" && "{VENV_PYTHON}" "{__file__}" {" ".join(sys.argv[1:])}'
        subprocess.run(cmd, shell=True)
        sys.exit()

    # Install required packages if not present (including Flask for the HTTP service)
    try:
        import fish_speech_lib
        import soundfile
        import flask
    except ImportError:
        print("Installing required Python packages (fish-speech-lib, soundfile, torchaudio, flask, flask-cors)...")
        packages = ['fish-speech-lib', 'soundfile', 'torchaudio', 'flask', 'flask-cors']
        subprocess.run([sys.executable, '-m', 'pip', 'install'] + packages, check=True)

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

ensure_venv()


from fish_speech_lib.inference import FishSpeech
import soundfile as sf
from flask import Flask, request, jsonify, send_file, Response
import io
import numpy as np
import tempfile
import traceback

# Optional torch check for CUDA device; fall back to cpu if torch not available
try:
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
except Exception:
    device = "cpu"

# Lazily initialized FishSpeech instance
_tts_instance = None


def get_tts():
    global _tts_instance
    if _tts_instance is None:
        logger.info(f"Initializing FishSpeech on device: {device}")
        _tts_instance = FishSpeech(device=device)
    return _tts_instance


def synthesize_bytes(text, ref_audio_path, ref_text, max_new_tokens=1000, chunk_length=1000):
    """
    Synthesize and return WAV bytes (RIFF) for the given inputs.

    We force the output WAV to 24000 Hz (24 kHz) to match kokoro's behavior.
    If the model returns audio at a different sample rate, perform a simple
    resampling using numpy interpolation to avoid adding heavy dependencies.
    """
    TARGET_SR = 24000

    tts = get_tts()
    sample_rate, audio_data = tts(
        text=text,
        reference_audio=ref_audio_path,
        reference_audio_text=ref_text,
        max_new_tokens=max_new_tokens,
        chunk_length=chunk_length
    )

    # Ensure numpy array and float32 dtype
    audio = np.asarray(audio_data).astype('float32')
    try:
        channels = 1 if audio.ndim == 1 else audio.shape[1]
    except Exception:
        channels = None

    logger.info(
        f"Synthesized audio: sample_rate={int(sample_rate)}, shape={audio.shape}, "
        f"dtype={audio.dtype}, channels={channels}"
    )

    def _resample_audio(aud, orig_sr, target_sr):
        if int(orig_sr) == int(target_sr):
            return aud
        # aud shape: (n_samples,) or (n_samples, channels)
        n_samples = aud.shape[0]
        new_len = int(round(n_samples * float(target_sr) / float(orig_sr)))
        if new_len <= 0:
            raise ValueError("Computed new length for resampling is <= 0")
        # Create new sample positions
        old_positions = np.linspace(0, n_samples - 1, num=n_samples)
        new_positions = np.linspace(0, n_samples - 1, num=new_len)
        if aud.ndim == 1:
            return np.interp(new_positions, old_positions, aud).astype('float32')
        else:
            # Process each channel separately
            channels = aud.shape[1]
            resampled = np.zeros((new_len, channels), dtype='float32')
            for ch in range(channels):
                resampled[:, ch] = np.interp(new_positions, old_positions, aud[:, ch])
            return resampled

    # Resample if needed
    if int(sample_rate) != TARGET_SR:
        try:
            logger.info(f"Resampling audio from {int(sample_rate)} Hz to {TARGET_SR} Hz")
            audio = _resample_audio(audio, int(sample_rate), TARGET_SR)
            sample_rate = TARGET_SR
            logger.info(f"Resampling complete: new shape={audio.shape}, dtype={audio.dtype}")
        except Exception as e:
            logger.warning(f"Resampling failed: {e}. Proceeding with original audio and sample rate.")

    # Ensure float32 and write WAV using the target sample rate
    audio = audio.astype('float32')
    wav_io = io.BytesIO()
    sf.write(wav_io, audio, int(sample_rate), format='WAV')
    wav_io.seek(0)
    return wav_io


# Flask app
app = Flask(__name__)


@app.route('/api/tts', methods=['POST'])
def http_tts():
    """
    POST JSON:
      {
        "text": "...",
        "ref_text": "...",
        "max_new_tokens": 1000,        # optional
        "chunk_length": 1000           # optional
      }
    Or multipart/form-data with file field "ref_audio" (wav) and form fields above.
    If a file is uploaded for ref_audio it will be used; otherwise a path string may be provided
    in the "ref_audio_path" JSON/form field (path on disk accessible by the service).
    """
    logger.info(f"Received TTS request from {request.remote_addr}")
    try:
        # Accept both JSON and form-data
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
            logger.error("No text provided in request")
            return jsonify({"error": "Text is required"}), 400
        # ref_text is optional; proceed with an empty string if not provided so the service can
        # still synthesize using the reference audio alone (if supported by the model).
        if not ref_text:
            logger.warning("No ref_text provided in request; proceeding with empty ref_text. Provide ref_text for better voice cloning quality.")
            ref_text = ""

        temp_file_path = None
        default_ref_audio = os.path.join(os.getcwd(), 'voices', 'default.wav')
        if uploaded_file:
            # Save uploaded reference audio to a temporary file
            tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            uploaded_file.save(tmpf.name)
            temp_file_path = tmpf.name
            ref_audio_to_use = temp_file_path
        elif ref_audio_path:
            # Use provided path on disk if it exists, otherwise fall back to default
            if os.path.exists(ref_audio_path):
                ref_audio_to_use = ref_audio_path
            else:
                logger.warning(f"Provided ref_audio_path {ref_audio_path} does not exist; attempting to use default reference audio.")
                if os.path.exists(default_ref_audio):
                    ref_audio_to_use = default_ref_audio
                    logger.warning(f"Using default reference audio at {default_ref_audio}")
                else:
                    logger.error(f"Provided ref_audio_path {ref_audio_path} not found and default reference audio './voices/default.wav' not found")
                    return jsonify({"error": "Reference audio not found (ref_audio_path invalid and ./voices/default.wav missing)"}), 400
        else:
            # No uploaded file and no path provided -> use default reference audio if available
            if os.path.exists(default_ref_audio):
                ref_audio_to_use = default_ref_audio
                logger.warning(f"No ref_audio provided; using default reference audio at {default_ref_audio}")
            else:
                logger.error("No ref_audio provided and default reference audio './voices/default.wav' not found")
                return jsonify({"error": "Reference audio is required (upload, ref_audio_path, or ./voices/default.wav)"}), 400

        wav_io = synthesize_bytes(text, ref_audio_to_use, ref_text, max_new_tokens=max_new_tokens, chunk_length=chunk_length)

        # Save a copy to ./outputs/output.wav for direct playback, then clean up temp file if created
        try:
            os.makedirs('outputs', exist_ok=True)
            out_path = os.path.join('outputs', 'output.wav')
            with open(out_path, 'wb') as out_f:
                out_f.write(wav_io.getvalue())
            logger.info(f"Saved generated audio to {out_path}")
        except Exception as e:
            logger.warning(f"Failed to save generated audio to ./outputs/output.wav: {e}")

        # Clean up temp file if created
        if temp_file_path:
            try:
                os.remove(temp_file_path)
            except Exception:
                logger.warning(f"Could not remove temp file {temp_file_path}")

        logger.info("Successfully generated audio")
        # Rewind buffer before sending
        wav_io.seek(0)
        return send_file(wav_io, mimetype='audio/wav', as_attachment=True, download_name='output.wav')

    except Exception as e:
        logger.error(f"Error generating audio: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/tts/stream', methods=['POST'])
def http_tts_stream():
    """
    Streamed endpoint. For compatibility it will generate audio and stream the WAV bytes as a single chunk.
    """
    logger.info(f"Received streaming TTS request from {request.remote_addr}")
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
            logger.error("No text provided in request")
            return jsonify({"error": "Text is required"}), 400
        # ref_text is optional for streaming as well; use empty string when absent.
        if not ref_text:
            logger.warning("No ref_text provided in request; proceeding with empty ref_text for streaming. Provide ref_text for better voice cloning quality.")
            ref_text = ""

        temp_file_path = None
        default_ref_audio = os.path.join(os.getcwd(), 'voices', 'default.wav')
        if uploaded_file:
            tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            uploaded_file.save(tmpf.name)
            temp_file_path = tmpf.name
            ref_audio_to_use = temp_file_path
        elif ref_audio_path:
            # Use provided path on disk if it exists, otherwise fall back to default
            if os.path.exists(ref_audio_path):
                ref_audio_to_use = ref_audio_path
            else:
                logger.warning(f"Provided ref_audio_path {ref_audio_path} does not exist; attempting to use default reference audio.")
                if os.path.exists(default_ref_audio):
                    ref_audio_to_use = default_ref_audio
                    logger.warning(f"Using default reference audio at {default_ref_audio}")
                else:
                    logger.error(f"Provided ref_audio_path {ref_audio_path} not found and default reference audio './voices/default.wav' not found")
                    return jsonify({"error": "Reference audio not found (ref_audio_path invalid and ./voices/default.wav missing)"}), 400
        else:
            # No uploaded file and no path provided -> use default reference audio if available
            if os.path.exists(default_ref_audio):
                ref_audio_to_use = default_ref_audio
                logger.warning(f"No ref_audio provided; using default reference audio at {default_ref_audio}")
            else:
                logger.error("No ref_audio provided and default reference audio './voices/default.wav' not found")
                return jsonify({"error": "Reference audio is required (upload, ref_audio_path, or ./voices/default.wav)"}), 400

        # Generate full WAV bytes synchronously and return them with explicit Content-Length.
        # Returning the full bytes ensures clients receive a complete WAV file with a correct header
        # and Content-Length which prevents some players from assuming an incorrect sample rate/format.
        try:
            wav_io = synthesize_bytes(text, ref_audio_to_use, ref_text, max_new_tokens=max_new_tokens, chunk_length=chunk_length)

            # Save a copy to ./outputs/output.wav for direct playback
            try:
                os.makedirs('outputs', exist_ok=True)
                out_path = os.path.join('outputs', 'output.wav')
                with open(out_path, 'wb') as out_f:
                    out_f.write(wav_io.getvalue())
                logger.info(f"Saved streamed-generated audio to {out_path}")
            except Exception as e:
                logger.warning(f"Failed to save streamed-generated audio to ./outputs/output.wav: {e}")

            data = wav_io.getvalue()
            # Build a full response with Content-Length to avoid player/sample-rate misinterpretation.
            resp = Response(data, mimetype='audio/wav')
            resp.headers['Content-Length'] = str(len(data))
            logger.info("Streamed audio (single chunk, returned as full response)")
        except Exception as e:
            logger.error(f"Error during streaming synthesis: {e}\n{traceback.format_exc()}")
            return jsonify({"error": str(e)}), 500

        # Clean up temp file if created (do it after generation)
        if temp_file_path:
            try:
                os.remove(temp_file_path)
            except Exception:
                logger.warning(f"Could not remove temp file {temp_file_path}")

        return resp

    except Exception as e:
        logger.error(f"Error preparing streaming response: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/status', methods=['GET'])
def status():
    logger.info(f"Status check from {request.remote_addr}")
    return jsonify({"status": "running", "device": device}), 200


if __name__ == '__main__':
    # Create outputs directory for compatibility with other scripts / examples
    os.makedirs('outputs', exist_ok=True)

    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting FishSpeech HTTP service on port {port} (device={device})")
    # Run Flask app
    app.run(host='0.0.0.0', port=port)

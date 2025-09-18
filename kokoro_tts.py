import os
import sys
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import io
import shutil
import textwrap

# Path to your virtualenv (using 'kokoro_env' name)
VENV_PATH = os.path.join(os.path.dirname(__file__), 'kokoro_env')

# Determine venv python path per-OS (no shell activation required)
if os.name == 'nt':
    _venv_bin = os.path.join(VENV_PATH, 'Scripts')
    VENV_PYTHON = os.path.join(_venv_bin, 'python.exe')
else:
    _venv_bin = os.path.join(VENV_PATH, 'bin')
    # Prefer 'python' inside venv; it's always present
    VENV_PYTHON = os.path.join(_venv_bin, 'python')

SUPPORTED_PYTHON_VERSIONS = ((3, 11),)


def _python_version_tuple(python_cmd):
    command = list(python_cmd) if isinstance(python_cmd, (list, tuple)) else [python_cmd]
    result = subprocess.check_output(
        command + ['-c', 'import sys; print("%d.%d" % sys.version_info[:2])'],
        text=True
    ).strip()
    major, minor = result.split('.')
    return int(major), int(minor)


def _normalize_python_spec(spec):
    if isinstance(spec, (list, tuple)):
        parts = list(spec)
    elif isinstance(spec, str):
        # Treat strings containing path separators as explicit paths (allow spaces)
        if any(sep in spec for sep in (os.sep, os.altsep) if sep):
            if os.path.exists(spec):
                return [spec]
            return None
        parts = spec.split()
    else:
        return None

    if not parts:
        return None

    resolved = parts[:]
    first = resolved[0]
    # Resolve commands available on PATH
    if os.path.basename(first) == first:
        located = shutil.which(first)
        if not located:
            return None
        resolved[0] = located
    else:
        if not os.path.exists(first):
            return None
    return resolved


def _resolve_bootstrap_python():
    """Locate a Python interpreter with a supported version for the venv."""
    env_override = os.environ.get('KOKORO_PYTHON')
    candidates = []
    if env_override:
        candidates.append(env_override)
    if sys.version_info[:2] in SUPPORTED_PYTHON_VERSIONS:
        candidates.append(sys.executable)
    candidates.append('python3.11')
    if os.name == 'nt':
        candidates.append('py -3.11')
    pyenv_root = os.environ.get('PYENV_ROOT', os.path.expanduser('~/.pyenv'))
    pyenv_versions = os.path.join(pyenv_root, 'versions')
    if os.path.isdir(pyenv_versions):
        for entry in sorted(os.listdir(pyenv_versions)):
            candidate_path = os.path.join(pyenv_versions, entry, 'bin', 'python3.11')
            candidates.append(candidate_path)

    for candidate in candidates:
        if not candidate:
            continue
        command = _normalize_python_spec(candidate)
        if not command:
            continue
        try:
            major, minor = _python_version_tuple(command)
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            continue
        if (major, minor) in SUPPORTED_PYTHON_VERSIONS:
            return command

    supported = ', '.join(f"{maj}.{min_}" for maj, min_ in SUPPORTED_PYTHON_VERSIONS)
    instructions = textwrap.dedent(
        f"""
        Python {supported} is required but was not found on this machine.

        Install Python 3.11 (pyenv recommended):
          git clone https://github.com/pyenv/pyenv.git ~/.pyenv
          export PYENV_ROOT="$HOME/.pyenv"
          command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
          eval "$(pyenv init -)"
          pyenv install 3.11.11

        After installing, make sure your system-level Python 3.11 has the CUDA-aware
        packages you need (e.g. torch with your CUDA wheel) so they can be shared.
        This launcher will reuse that Python 3.11 interpreter inside the kokoro_env
        virtualenv, borrowing the CUDA stack from the system install and installing
        all remaining packages in the venv.

        If Python 3.11 lives at a custom path, set KOKORO_PYTHON to that interpreter
        before starting this script.
        """
    ).strip()
    raise RuntimeError(instructions)

def ensure_venv():
    bootstrap_cmd = _resolve_bootstrap_python()

    def venv_python_supported():
        if not os.path.exists(VENV_PYTHON):
            return False
        try:
            major, minor = _python_version_tuple(VENV_PYTHON)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
        return (major, minor) in SUPPORTED_PYTHON_VERSIONS

    # Check if we're in the virtualenv
    if os.path.normpath(sys.prefix) != os.path.normpath(VENV_PATH):
        # Create or rebuild the venv if needed
        if not venv_python_supported():
            if os.path.exists(VENV_PATH):
                print("Recreating virtualenv to use a supported Python version...")
                shutil.rmtree(VENV_PATH)
            logger.info("Reusing system Python 3.11 interpreter at %s for kokoro_env", bootstrap_cmd[0])
            print("Creating virtualenv with system packages...")
            subprocess.run(bootstrap_cmd + ['-m', 'venv', VENV_PATH, '--system-site-packages'], check=True)
        # Re-run the script using the venv's Python directly (cross-platform)
        print("Re-running with virtualenv Python...")
        subprocess.run([VENV_PYTHON, __file__, *sys.argv[1:]], check=True)
        sys.exit()
    # List of required packages with versions where needed
    requirements = [
        'torch==2.8.0+cu128',
        'numpy',
        'soundfile',
        'kokoro',
        'misaki[en]',
        'flask',
        'flask-cors',
        'torchfile'
    ]
    CUDA_INDEX_URL = 'https://download.pytorch.org/whl/cu128'
    for pkg in requirements:
        try:
            __import__(pkg.split('==')[0].split('[')[0])  # Check if importable
        except ImportError as e:
            print(f"Installing {pkg}...")
            cmd = [sys.executable, '-m', 'pip', 'install', pkg]
            if pkg.startswith('torch=='):
                cmd.extend(['--index-url', CUDA_INDEX_URL])
            subprocess.run(cmd, check=True)

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
        logger.info("Initializing Kokoro pipeline and downloading model weights if needed")
        pipeline = KPipeline(lang_code='a', device=device)  # American English, use detected device
    return pipeline


# Warm the pipeline during startup so required assets download before handling traffic
get_pipeline()

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

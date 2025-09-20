import os
import sys
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import io
import shutil
import textwrap

# NOTE: This launcher prefers to run inside a Conda environment. If a suitable
# Conda env (name controlled by `KOKORO_CONDA_ENV`, default `kokoro`) exists
# it will be activated. If it does not exist the script will create it and
# re-exec inside that env. The script will avoid using the system Python
# unless the user explicitly requests it with the `--use-system-python`
# command-line flag or `KOKORO_ALLOW_SYSTEM_PYTHON=1` environment variable.

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
    """Locate a Python interpreter with a supported version for running the service."""
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

        After installing, make sure your Python 3.11 has the CUDA-aware packages
        you need (e.g. a compatible torch). This launcher will reuse that
        interpreter (or a Conda environment) to run the service and will install
        any missing Python packages into the active interpreter.

        If Python 3.11 lives at a custom path, set KOKORO_PYTHON to that interpreter
        before starting this script.
        """
    ).strip()
    raise RuntimeError(instructions)

def ensure_environment():
    """Ensure we're running inside a supported interpreter, preferring Conda.

    Behavior:
      - If `--use-system-python` is passed or `KOKORO_ALLOW_SYSTEM_PYTHON=1`
        the script may use the current system interpreter (subject to version
        checks and `KOKORO_PYTHON`).
      - Otherwise the script will attempt to find `conda`, activate an env
        named by `KOKORO_CONDA_ENV` (default `kokoro`), create it if missing,
        and re-exec inside that env. If `conda` is not available it falls back
        to locating a suitable Python via `_resolve_bootstrap_python`.
    """
    allow_system = ('--use-system-python' in sys.argv) or (os.environ.get('KOKORO_ALLOW_SYSTEM_PYTHON') == '1')
    conda_env_name = os.environ.get('KOKORO_CONDA_ENV', 'kokoro')

    # Defer resolving a bootstrap python until after attempting Conda-based
    # activation/creation. `_resolve_bootstrap_python` may raise if no
    # suitable interpreter exists; we only want to call it as a fallback.
    bootstrap_cmd = None

    def _is_conda_python(python_cmd):
        """Return True if the given python interpreter belongs to a Conda env."""
        command = list(python_cmd) if isinstance(python_cmd, (list, tuple)) else [python_cmd]
        try:
            result = subprocess.check_output(
                command + ['-c', 'import sys, os; print(os.path.isdir(os.path.join(sys.prefix, "conda-meta")))'],
                text=True
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
        return result.lower() in ('1', 'true', 'yes')

    # Determine whether we're already executing in a target environment where
    # we can proceed to install missing Python packages. We avoid returning
    # early so package installation runs even if we're already inside Conda
    # or using the system interpreter (when allowed).
    executing_in_target_env = False
    if sys.version_info[:2] in SUPPORTED_PYTHON_VERSIONS:
        if _is_conda_python(sys.executable):
            logger.info("Running inside Conda environment at %s", sys.prefix)
            executing_in_target_env = True
        elif allow_system:
            logger.info("Using non-Conda supported Python %s.%s as requested", *sys.version_info[:2])
            executing_in_target_env = True

    # If we're not already in a suitable environment, prefer using conda if
    # available to create/activate one and re-exec inside it.
    # Otherwise we'll fall back to locating a suitable Python interpreter.
    if not executing_in_target_env:
        conda_cmd = shutil.which('conda')
        if (conda_cmd is not None) and (not allow_system):
            try:
                # Check existing envs via `conda env list --json`
                out = subprocess.check_output([conda_cmd, 'env', 'list', '--json'], text=True)
                import json
                envs = json.loads(out).get('envs', [])
                target_prefix = None
                for p in envs:
                    if os.path.basename(p) == conda_env_name or p.rstrip(os.path.sep).endswith(os.path.sep + conda_env_name):
                        target_prefix = p
                        break

                if target_prefix:
                    print(f"Activating existing Conda environment '{conda_env_name}'...", flush=True)
                    # Use `--no-capture-output` so the child process stdout/stderr are
                    # forwarded to the terminal (important for long-running installs).
                    subprocess.run([conda_cmd, 'run', '--no-capture-output', '-n', conda_env_name, 'python', __file__, *sys.argv[1:]], check=True)
                    sys.exit()
                else:
                    print(f"Creating Conda environment '{conda_env_name}' with Python 3.11...", flush=True)
                    subprocess.run([conda_cmd, 'create', '-n', conda_env_name, 'python=3.11', '-y'], check=True)
                    print("Re-running inside newly created Conda environment...", flush=True)
                    subprocess.run([conda_cmd, 'run', '--no-capture-output', '-n', conda_env_name, 'python', __file__, *sys.argv[1:]], check=True)
                    sys.exit()
            except subprocess.CalledProcessError:
                logger.warning("Conda command failed; falling back to other resolution methods")

        # If conda is not available (or user allowed system Python), fall back to
        # the previous bootstrap behaviour: locate a compatible Python and re-exec.
        try:
            if bootstrap_cmd is None:
                bootstrap_cmd = _resolve_bootstrap_python()
        except RuntimeError:
            # No suitable bootstrap python found; surface the helpful error
            # instructions from `_resolve_bootstrap_python`.
            raise

        if bootstrap_cmd:
            # If the bootstrap candidate is the current interpreter, and allowed,
            # continue; otherwise re-exec under the bootstrap interpreter.
            if isinstance(bootstrap_cmd, (list, tuple)):
                bootstrap_exe = bootstrap_cmd[0]
            else:
                bootstrap_exe = bootstrap_cmd

            try:
                # If bootstrap_exe is the same as current exe and system allowed, continue
                if os.path.abspath(str(bootstrap_exe)) == os.path.abspath(sys.executable) or allow_system:
                    logger.info("Using current interpreter %s", sys.executable)
                    executing_in_target_env = True
                else:
                    print("Re-running with supported Python interpreter...", flush=True)
                    subprocess.run(list(bootstrap_cmd) + [__file__, *sys.argv[1:]], check=True)
                    sys.exit()
            except Exception:
                # Best-effort fallback: if we can't re-exec, raise
                raise
        else:
            raise RuntimeError("No suitable Python interpreter available.")

    # At this point we should be running inside a supported interpreter (Conda
    # env or allowed system interpreter). Proceed to ensure required packages
    # are installed into the active interpreter.
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
            print(f"Installing {pkg}...", flush=True)
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

# Ensure a supported Python interpreter / Conda environment is active
ensure_environment()

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

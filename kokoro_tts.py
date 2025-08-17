import os
import sys
import subprocess

# Path to your virtualenv (adjust if needed; assumes same dir as script)
VENV_PATH = os.path.join(os.path.dirname(__file__), 'kokoro_env')
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

def install_dependencies():
    # List of required packages with versions where needed
    requirements = [
        'torch==2.8.0',
        'kokoro',
        'misaki[en]',
        'soundfile'
    ]
    for pkg in requirements:
        try:
            __import__(pkg.split('==')[0].split('[')[0])  # Check if importable
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], check=True)

# Ensure virtualenv is active
ensure_venv()

# Install dependencies if missing
install_dependencies()

# Original script imports (now safe after installs)
import torch
import soundfile as sf
from kokoro import KPipeline

def main(text):
    pipeline = KPipeline(lang_code='a')  # American English
    voice = 'af_heart'
    generator = pipeline(text, voice=voice, speed=1.0)
    for i, (gs, ps, audio) in enumerate(generator):
        output_file = f'output_{i}.wav'
        sf.write(output_file, audio, 24000)
        print(f"Saved audio chunk {i} to {output_file}")
        print(f"Graph: {gs}")
        print(f"Phonemes: {ps}")

if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "Hello, this is a test using Kokoro TTS."
    main(text)
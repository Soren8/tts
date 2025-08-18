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

    # Install fish-speech-lib and soundfile if not present
    try:
        import fish_speech_lib
        import soundfile
    except ImportError:
        print("Installing fish-speech-lib, soundfile, and torchaudio...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'fish-speech-lib', 'soundfile', 'torchaudio'], check=True)

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)

ensure_venv()

# Create .project-root file before importing fish speech library
project_root_file = '.project-root'
if not os.path.exists(project_root_file):
    Path(project_root_file).touch()
    logger.info("Created .project-root file")

from fish_speech_lib.inference import FishSpeech
import soundfile as sf


def text_to_speech(text, ref_audio, ref_text, output_file='output.wav', device='cuda', max_new_tokens=1000, chunk_length=1000):
    tts = FishSpeech(device=device)
    sample_rate, audio_data = tts(
        text=text,
        reference_audio=ref_audio,
        reference_audio_text=ref_text,
        max_new_tokens=max_new_tokens,
        chunk_length=chunk_length
    )
    sf.write(output_file, audio_data, sample_rate, format='WAV')
    logger.info(f"Audio generated at {output_file}")

if __name__ == '__main__':
    ref_audio = 'voices/default.wav'  # Reference audio file
    ref_text = 'Your reference text here.'  # Replace with the exact transcript of the reference audio
    text = 'Hello, this is a test of Fish Speech text-to-speech with voice cloning.'

    text_to_speech(text, ref_audio, ref_text)

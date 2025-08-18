import os
import sys
import subprocess
import logging
import shutil

# Path to Fish Speech repo
REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'fish-speech'))
VENV_PATH = os.path.join(REPO_PATH, 'fishspeech_venv')
VENV_PYTHON = os.path.join(VENV_PATH, 'bin', 'python') if os.name != 'nt' else os.path.join(VENV_PATH, 'Scripts', 'python.exe')
VENV_ACTIVATE = os.path.join(VENV_PATH, 'bin', 'activate') if os.name != 'nt' else os.path.join(VENV_PATH, 'Scripts', 'activate.bat')

def ensure_repo():
    if not os.path.exists(REPO_PATH):
        print("Cloning Fish Speech repository...")
        subprocess.run(['git', 'clone', 'https://github.com/fishaudio/fish-speech.git', REPO_PATH], check=True)

def ensure_venv():
    ensure_repo()
    os.chdir(REPO_PATH)  # Change to repo dir for installations and runs

    # Check if we're in the virtualenv
    if os.path.normpath(sys.prefix) != os.path.normpath(VENV_PATH):
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

    # Install huggingface-hub with cli if not present
    try:
        import huggingface_hub
    except ImportError:
        print("Installing huggingface-hub[cli]...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'huggingface-hub[cli]'], check=True)

    # Install the package if not already
    try:
        import fish_speech
    except ImportError:
        print("Installing Fish Speech...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-e', '.'], check=True)

# Download checkpoints if not present
def ensure_checkpoints():
    s1_mini_dir = os.path.join('checkpoints', 'openaudio-s1-mini')
    if not os.path.exists(s1_mini_dir):
        print("Downloading OpenAudio S1 Mini checkpoints...")
        subprocess.run(['huggingface-cli', 'download', 'fishaudio/openaudio-s1-mini', '--local-dir', s1_mini_dir], check=True)

    vqgan_dir = os.path.join('checkpoints', 'fish-speech-vqgan')
    if not os.path.exists(vqgan_dir):
        print("Downloading Fish Speech VQGAN checkpoints...")
        subprocess.run(['huggingface-cli', 'download', 'fishaudio/fish-speech-vqgan', '--local-dir', vqgan_dir], check=True)

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)

ensure_venv()
ensure_checkpoints()

# Now the test app code

def create_temp_dir():
    temp_dir = 'tts_temp'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    return temp_dir

def prepare_reference(ref_audio, ref_text, temp_dir='tts_temp'):
    # Copy ref_audio to temp_dir
    ref_audio_temp = os.path.join(temp_dir, os.path.basename(ref_audio))
    shutil.copy(ref_audio, ref_audio_temp)

    # For Fish Speech, the prompt text is used directly, no .lab needed

    # Run vqgan to get prompt tokens from ref audio
    vqgan_checkpoint = 'checkpoints/fish-speech-vqgan/group_1-vqgan.ckpt'
    prompt_tokens = os.path.join(temp_dir, 'prompt_tokens.npy')
    subprocess.run([
        VENV_PYTHON, '-m', 'tools.vqgan_infer',
        '--mode', 'encode',
        '--checkpoint-path', vqgan_checkpoint,
        '--input-audio', ref_audio_temp,
        '--output-tokens', prompt_tokens
    ], cwd=os.getcwd(), check=True)  # cwd is repo dir

    return prompt_tokens, ref_text

def text_to_semantic(text, prompt_text, prompt_tokens, temp_dir='tts_temp'):
    codes_file = os.path.join(temp_dir, 'codes.npy')
    s1_mini_checkpoint = 'checkpoints/openaudio-s1-mini/decoder.ckpt'
    config_path = 'checkpoints/openaudio-s1-mini/config.json'
    tokenizer_path = 'checkpoints/openaudio-s1-mini/tokenizer.json'

    subprocess.run([
        VENV_PYTHON, '-m', 'tools.text2semantic_infer',
        '--text', text,
        '--prompt-text', prompt_text,
        '--prompt-tokens', prompt_tokens,
        '--checkpoint-path', s1_mini_checkpoint,
        '--config-path', config_path,
        '--tokenizer', tokenizer_path,
        '--output-path', codes_file
    ], cwd=os.getcwd(), check=True)

    return codes_file

def semantic_to_audio(codes_file, output_file, temp_dir='tts_temp'):
    vqgan_checkpoint = 'checkpoints/fish-speech-vqgan/group_1-vqgan.ckpt'
    generated_audio = os.path.join(temp_dir, 'fake.wav')
    subprocess.run([
        VENV_PYTHON, '-m', 'tools.vqgan_infer',
        '--mode', 'decode',
        '--checkpoint-path', vqgan_checkpoint,
        '--input-tokens', codes_file,
        '--output-audio', generated_audio
    ], cwd=os.getcwd(), check=True)

    # Copy to output_file
    shutil.copy(generated_audio, output_file)

if __name__ == '__main__':
    # Example usage
    ref_audio = 'path/to/your/ref_audio.wav'  # Replace with your reference audio file path
    ref_text = 'Your reference text here.'    # Replace with the exact transcript of the reference audio
    text = 'Hello, this is a test of OpenAudio S1 text-to-speech.'  # The text to convert to speech
    output_file = 'output.wav'                # Output audio file

    temp_dir = create_temp_dir()

    prompt_tokens, prompt_text = prepare_reference(ref_audio, ref_text, temp_dir=temp_dir)
    codes_file = text_to_semantic(text, prompt_text, prompt_tokens, temp_dir=temp_dir)
    semantic_to_audio(codes_file, output_file, temp_dir=temp_dir)

    print(f'Audio generated at {output_file}')

    # Optional: Clean up temp dir
    # shutil.rmtree(temp_dir)
import sys
from TTS.utils.manage import ModelManager
import os

def download_model():
    # Create a pipe to simulate input
    r, w = os.pipe()
    
    # Temporarily redirect stdin to our pipe
    old_stdin = os.dup(0)
    os.dup2(r, 0)
    
    try:
        # Write 'y' to the pipe
        os.write(w, b'y\n')
        
        # Download the model
        ModelManager().download_model("tts_models/multilingual/multi-dataset/xtts_v2")
        
    finally:
        # Restore original stdin
        os.dup2(old_stdin, 0)
        os.close(r)
        os.close(w)

if __name__ == "__main__":
    download_model()

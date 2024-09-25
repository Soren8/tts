import torch
from transformers import AutoProcessor, AutoModelForTextToWaveform
import scipy.io.wavfile as wavfile
import numpy as np
import sounddevice as sd

# Check for CUDA availability
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Load the model and processor
model_name = "parler-tts/parler-tts-mini-v1"
processor = AutoProcessor.from_pretrained(model_name)
model = AutoModelForTextToWaveform.from_pretrained(model_name).to(device)

while True:
    # Text to synthesize
    text = input("Enter the text you want to convert to speech (or 'quit' to exit): ")
    
    if text.lower() == 'quit':
        break

    # Prepare the input
    inputs = processor(text=text, return_tensors="pt").to(device)

    # Generate the audio
    with torch.no_grad():
        output = model.generate(**inputs)

    # Get the audio data
    audio = output.audio.cpu().numpy().squeeze()

    # Normalize the audio
    audio = audio / np.max(np.abs(audio))

    # Get the sample rate
    sample_rate = model.config.sample_rate

    # Play the audio
    print("Playing audio...")
    sd.play(audio, sample_rate)
    sd.wait()  # Wait until the audio is finished playing

    # Optionally, save the audio file
    wavfile.write("output.wav", sample_rate, (audio * 32767).astype(np.int16))
    print("Audio file 'output.wav' has been generated.")

    # Print CUDA memory usage if available
    if torch.cuda.is_available():
        print(f"CUDA memory allocated: {torch.cuda.memory_allocated()/1e6:.2f} MB")
        print(f"CUDA memory reserved: {torch.cuda.memory_reserved()/1e6:.2f} MB")

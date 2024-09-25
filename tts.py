import torch
from transformers import AutoProcessor, AutoModel
import scipy.io.wavfile as wavfile
import numpy as np
import sounddevice as sd

# Check for CUDA availability
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Load the model and processor
model_name = "suno/bark-small"
processor = AutoProcessor.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name).to(device)

while True:
    # Text to synthesize
    text = input("Enter the text you want to convert to speech: ")

    # Prepare the input
    inputs = processor(text, voice_preset="v2/en_speaker_0", return_tensors="pt").to(device)

    # Generate the audio
    with torch.no_grad():
        output = model.generate(**inputs)

    # Convert the output to a numpy array
    audio = output.cpu().numpy().squeeze()

    # Normalize the audio
    audio = audio / np.max(np.abs(audio))

    # Get the sample rate from the model's configuration
    sample_rate = model.generation_config.sample_rate

    # Play the audio
    print("Playing audio...")
    sd.play(audio, sample_rate)
    sd.wait()  # Wait until the audio is finished playing

    # Optionally, still save the audio file
    wavfile.write("output.wav", sample_rate, (audio * 32767).astype(np.int16))
    print("Audio file 'output.wav' has been generated.")

    # Print CUDA memory usage if available
    if torch.cuda.is_available():
        print(f"CUDA memory allocated: {torch.cuda.memory_allocated()/1e6:.2f} MB")
        print(f"CUDA memory cached: {torch.cuda.memory_reserved()/1e6:.2f} MB")
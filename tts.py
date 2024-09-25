import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
import scipy.io.wavfile as wavfile
import numpy as np
import sounddevice as sd

# Check for CUDA availability
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Load the model and tokenizer
model_name = "parler-tts/parler-tts-mini-v1"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = ParlerTTSForConditionalGeneration.from_pretrained(model_name).to(device)

# Default description
description = "A female speaker delivers a slightly expressive and animated speech with a moderate speed and pitch. The recording is of very high quality, with the speaker's voice sounding clear and very close up."

while True:
    # Text to synthesize
    text = input("Enter the text you want to convert to speech (or 'quit' to exit): ")
    
    if text.lower() == 'quit':
        break

    # Prepare the input
    input_ids = tokenizer(description, return_tensors="pt").input_ids.to(device)
    prompt_input_ids = tokenizer(text, return_tensors="pt").input_ids.to(device)

    # Generate the audio
    with torch.no_grad():
        generation = model.generate(input_ids=input_ids, prompt_input_ids=prompt_input_ids)

    # Get the audio data
    audio = generation.cpu().numpy().squeeze()

    # Normalize the audio
    audio = audio / np.max(np.abs(audio))

    # Get the sample rate
    sample_rate = model.config.sampling_rate

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
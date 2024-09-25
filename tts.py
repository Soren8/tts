import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
import scipy.io.wavfile as wavfile
import numpy as np
import sounddevice as sd
import soundfile as sf

# Check for CUDA availability
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Load the model and tokenizer
model_name = "parler-tts/parler-tts-mini-jenny-30H"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = ParlerTTSForConditionalGeneration.from_pretrained(model_name).to(device)

# Default description
description = "Jenny delivers a slightly expressive and animated speech with a moderate speed and pitch. The recording is of very high quality, with the speaker's voice sounding clear and very close up."

while True:
    # Text to synthesize
    text = input("Enter the text you want to convert to speech (or 'quit' to exit): ")
    
    if text.lower() == 'quit':
        break

    # Prepare the input
    input_ids = tokenizer(description, return_tensors="pt").input_ids.to(device)
    prompt_input_ids = tokenizer(text, return_tensors="pt").input_ids.to(device)

    # Generate the audio
    generation = model.generate(input_ids=input_ids, prompt_input_ids=prompt_input_ids)
    audio = generation.cpu().numpy().squeeze()

    # Normalize the audio
    audio = audio / np.max(np.abs(audio))

    # Play the audio
    print("Playing audio...")
    sd.play(audio, model.config.sampling_rate)
    sd.wait()  # Wait until the audio is finished playing

    # Optionally, save the audio file
    #sf.write("output.wav", audio, model.config.sampling_rate)
    #print("Audio file 'output.wav' has been generated.")

    # Print CUDA memory usage if available
    if torch.cuda.is_available():
        print(f"CUDA memory allocated: {torch.cuda.memory_allocated()/1e6:.2f} MB")
        print(f"CUDA memory reserved: {torch.cuda.memory_reserved()/1e6:.2f} MB")
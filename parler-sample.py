import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
import soundfile as sf

device = "cuda:0" if torch.cuda.is_available() else "cpu"

model = ParlerTTSForConditionalGeneration.from_pretrained("parler-tts/parler-tts-mini-jenny-30H").to(device)
tokenizer = AutoTokenizer.from_pretrained("parler-tts/parler-tts-mini-jenny-30H")

prompt = "Hey, how are you doing today? My name is Jenny, and I'm here to help you with any questions you have."
description = "Jenny speaks at fast pace with an excited delivery in a very confined sounding environment with clear audio quality."

input_ids = tokenizer(description, return_tensors="pt").input_ids.to(device)
prompt_input_ids = tokenizer(prompt, return_tensors="pt").input_ids.to(device)

generation = model.generate(input_ids=input_ids, prompt_input_ids=prompt_input_ids)
audio_arr = generation.cpu().numpy().squeeze()
sf.write("parler_tts_out.wav", audio_arr, model.config.sampling_rate)

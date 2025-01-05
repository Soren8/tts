# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (PortAudio)
RUN apt-get update && apt-get install -y libportaudio2 && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Create a directory for pip cache
RUN mkdir -p /root/.cache/pip

# Install Python dependencies with pip cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Patch the TTS library to automatically accept the license
RUN sed -i 's/def ask_tos(self, output_path):/def ask_tos(self, output_path):\n        print("Automatically accepting Coqui Public Model License (CPML)")\n        return True/' /usr/local/lib/python3.9/site-packages/TTS/utils/manage.py

# Verify the patch was applied
RUN cat /usr/local/lib/python3.9/site-packages/TTS/utils/manage.py | grep -A 2 "def ask_tos"

# Pre-download the TTS model
RUN python -c "from TTS.utils.manage import ModelManager; ModelManager().download_model('tts_models/multilingual/multi-dataset/xtts_v2')"

# Copy the rest of the application code
COPY . .

# Create necessary directories
RUN mkdir -p outputs voices text

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application
CMD ["python", "xtts2.py"]

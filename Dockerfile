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

# Copy the download script
COPY download_model.py .

# Pre-download the TTS model using our script
RUN python download_model.py

# Remove XTTS-specific model (if exists) since kokoro uses different model
RUN rm -rf ~/.local/share/tts/tts_models--multilingual--multi-dataset--xtts_v2

# Copy the rest of the application code
COPY . .

# Create necessary directories
RUN mkdir -p outputs voices text

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application
CMD ["python", "kokoro_tts.py"]

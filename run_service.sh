#!/bin/bash

# Ensure uv is installed
if ! command -v uv &> /dev/null; then
    echo "uv is not installed. Please install it first: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Get the service to run from argument, default to kokoro_tts.py
SERVICE_SCRIPT=${1:-kokoro_tts.py}

if [ ! -f "$SERVICE_SCRIPT" ]; then
    echo "Error: Service script '$SERVICE_SCRIPT' not found."
    echo "Usage: ./run_service.sh [script_name.py]"
    exit 1
fi

echo "Starting TTS service: $SERVICE_SCRIPT using uv..."

export UV_HTTP_TIMEOUT=600

uv run "$SERVICE_SCRIPT"

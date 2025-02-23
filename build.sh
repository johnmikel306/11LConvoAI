#!/bin/bash
set -e  # Exit on error

# Clear pip cache
echo "Clearing pip cache..."
pip cache purge || true

# Install system dependencies
echo "Installing system dependencies..."
apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio

# Verify system packages
echo "Verifying installed packages..."
dpkg -l portaudio19-dev python3-pyaudio

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "Build completed successfully!"

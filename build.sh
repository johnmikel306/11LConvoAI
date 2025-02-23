#!/bin/bash

# Install system dependencies
sudo apt-get update && sudo apt-get install -y \
    portaudio19-dev \
    python3-dev

# Install Python dependencies
pip install -r requirements.txt

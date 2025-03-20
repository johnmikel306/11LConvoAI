#!/bin/bash
set -e  # Exit on error

# Clear pip cache
echo "Clearing pip cache..."
pip cache purge || true

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "Build completed successfully!"

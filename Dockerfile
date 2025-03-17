# Docker configuration
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies and Python packages
COPY requirements.txt .
RUN apt-get update && apt-get install -y \
    build-essential \
    portaudio19-dev \
    python3-dev \
    && pip install --no-cache-dir -r requirements.txt

# Copy the content of the local src directory to the working directory
COPY . .

# Expose the port the app runs on
EXPOSE 8888

# Set environment variables
ENV FLASK_APP=run.py
ENV FLASK_ENV=production

# Command to run on container start
CMD ["python", "run.py"]
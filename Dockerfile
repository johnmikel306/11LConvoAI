# Use the official Python image as a parent image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    portaudio19-dev \
    python3-dev

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the content of the local directory to the container's working directory
COPY . .

# Expose the port the app runs on (8888)
EXPOSE 8888

# Set environment variables for the Flask app
ENV FLASK_APP=run.py
ENV FLASK_ENV=production

# Command to run on container start
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:8888", "app:app"]
# Use the official Python image as a parent image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

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

# Run the Flask app when the container starts
CMD ["python", "run.py"]
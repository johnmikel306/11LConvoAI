# Use the official Python image as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the content of the local directory to the container's working directory
COPY . .

# Expose the port the app runs on (8888)
EXPOSE 8888

# Command to run on container start
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888"]
# ElevenLabs Conversational AI

## Description
A Flask application that utilizes the ElevenLabs API for conversational AI.

## Installation

### Using Docker
1. Build the Docker image:
   ```bash
   docker build -t elevenlabs-chat .
   ```
2. Run the Docker container:
   ```bash
   docker run -p 8888:8888 elevenlabs-chat
   ```

### Using pip
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```
2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
Run the application:
```bash
python run.py
```
Access the application at `http://localhost:8888`.

## Endpoints
- **`/`**: Renders the index page.
- **`/start`**: Starts a conversation.
- **`/stop`**: Stops the conversation.
- **`/transcript`**: Retrieves the conversation transcript.
- **`/welcome`**: Returns a welcome message.

## Dependencies
- Flask==2.3.2
- Flask-SocketIO==5.3.4
- python-dotenv==1.0.0
- eventlet==0.33.3
- elevenlabs
- gunicorn==20.1.0
- elevenlabs[pyaudio]==1.0.0
- new_dependency==1.0.0

## Environment Variables
- `SECRET_KEY`: Secret key for the Flask application.
- `AGENT_ID`: Agent ID for ElevenLabs API.
- `ELEVENLABS_API_KEY`: API key for ElevenLabs.

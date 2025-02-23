import os
import signal
import sys
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

# Initialize Flask app
app = Flask(__name__)
socketio = SocketIO(app)

# Load environment variables
load_dotenv()
AGENT_ID = os.getenv('AGENT_ID')
API_KEY = os.getenv('ELEVENLABS_API_KEY')
conversation = None
chat_history = []

# Store chat messages
def store_message(sender, message):
    chat_history.append({'sender': sender, 'message': message})
    socketio.emit('new_message', {'sender': sender, 'message': message})

# Initialize conversation
def initialize_conversation():
    global conversation
    if not AGENT_ID:
        raise Exception("AGENT_ID environment variable must be set")
    
    client = ElevenLabs(api_key=API_KEY)
    conversation = Conversation(
        client,
        AGENT_ID,
        requires_auth=bool(API_KEY),
        audio_interface=DefaultAudioInterface(),
        callback_agent_response=lambda response: store_message('agent', response),
        callback_user_transcript=lambda transcript: store_message('user', transcript),
    )
    conversation.start_session()
    return conversation._conversation_id

# API Endpoints
@app.route('/start', methods=['POST'])
def start_conversation():
    try:
        conv_id = initialize_conversation()
        return jsonify({'status': 'success', 'conversation_id': conv_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stop', methods=['POST'])
def stop_conversation():
    global conversation
    if conversation:
        try:
            conversation.end_session()
        except Exception as e:
            print(f"Error ending session: {e}")
        finally:
            conversation = None
    return jsonify({'status': 'success'})

@app.route('/transcript', methods=['GET'])
def get_transcript():
    return jsonify({'transcript': chat_history})

# Add route for main page
@app.route('/')
def index():
    return render_template('index.html')

# Run server
if __name__ == '__main__':
    socketio.run(app, debug=True)
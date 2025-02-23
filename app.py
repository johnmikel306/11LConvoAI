import os
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation

# Initialize Flask app
app = Flask(__name__)
socketio = SocketIO(app)

# Load environment variables
AGENT_ID = os.environ.get('AGENT_ID')
API_KEY = os.environ.get('ELEVENLABS_API_KEY')

# Initialize conversation
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
        conversation.end_session()
        conversation = None
    return jsonify({'status': 'success'})

@app.route('/transcript', methods=['GET'])
def get_transcript():
    return jsonify({'transcript': chat_history})

# Serve the frontend
@app.route('/')
def index():
    return render_template('index.html')

# Run the app
if __name__ == '__main__':
    # Use Gunicorn in production
    if os.environ.get('RENDER'):
        socketio.run(app, host='0.0.0.0', port=10000, allow_unsafe_werkzeug=True)
    else:
        # Use Flask's development server for local testing
        socketio.run(app, debug=True)
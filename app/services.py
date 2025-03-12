from .models import User
import os
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from .models import User

from flask import jsonify
import logging

# Interact with the database
async def create_user(email):
    user = User(email=email)  # Ensure the user is created with email
    await user.save_to_db()  # Save the user to the database
    return user

async def get_user_by_email(email):
    return await User.find_by_email(email)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
AGENT_ID = os.getenv('AGENT_ID')
API_KEY = os.getenv('ELEVENLABS_API_KEY')

# Global variables
conversation = None
chat_history = []

# Store chat messages
def store_message(sender, message):
    chat_history.append({'sender': sender, 'message': message})

# Initialize conversation
def initialize_conversation():
    global conversation
    if not AGENT_ID:
        logger.error("AGENT_ID environment variable must be set")
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
    logger.info("Conversation initialized with ID: %s", conversation._conversation_id)
    return conversation

def get_signed_url():
    if not AGENT_ID:
        logger.error("AGENT_ID environment variable must be set")
        raise Exception("AGENT_ID environment variable must be set")
    client = ElevenLabs(api_key=API_KEY)
    signed_url = client.conversational_ai.get_signed_url(AGENT_ID)
    return signed_url

# API Endpoints
def start_conversation():
    try:
        conversation = initialize_conversation()
        conversation.start_session()
        conv_id = conversation._conversation_id
        logger.info("Conversation started with ID: %s", conv_id)
        return jsonify({'status': 'success', 'conversation_id': conv_id})
    except Exception as e:
        logger.error("Error starting conversation: %s", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500

def stop_conversation():
    global conversation
    if conversation:
        conversation.end_session()
        logger.info("Conversation ended")
        conversation = None
    return jsonify({'status': 'success'})

def get_transcript():
    logger.info("Fetching transcript")
    return jsonify({'transcript': chat_history})

def get_signed_url_endpoint():
    try:
        signed_url = get_signed_url()
        return jsonify({'signed_url': signed_url})
    except Exception as e:
        logger.error(f"Error getting signed URL: {e}")
        return jsonify({'error': 'Failed to get signed URL'}), 500


from .models import User
import os
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from .models import User
from datetime import datetime
from .models import ConversationLog, Grade

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
        audio_interface= DefaultAudioInterface(),
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
    signed_url = client.conversational_ai.get_signed_url(agent_id=AGENT_ID)
    return signed_url.signed_url

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

async def stop_conversation():
    global conversation, chat_history
    try:
        if conversation:
            # Stop the conversation
            conversation.end_session()
            logger.info("Conversation ended")

            # Save the conversation transcript to the database
            conversation_id = conversation._conversation_id
            await save_conversation_to_db(conversation_id, chat_history)

            # Clear the conversation and chat history
            conversation = None
            chat_history = []

            return jsonify({'status': 'success', 'message': 'Conversation stopped and saved.'})
        else:
            return jsonify({"status": "error", "message": "No active conversation to stop."}), 400
    except Exception as e:
        logger.error(f"Error stopping conversation: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

async def save_conversation_to_db(conversation_id, transcript, current_user):
    """
    Save the conversation transcript and metadata to MongoDB.
    """
    try:
        conversation_log = ConversationLog(
            conversation_id=conversation_id,
            transcript=transcript,
            user_id=current_user,
            timestamp=datetime.utcnow()
        )
        await conversation_log.insert()
        logger.info(f"Conversation {conversation_id} saved to database.")
    except Exception as e:
        logger.error(f"Error saving conversation to database: {e}")
        raise e

def get_transcript():
    return jsonify({'transcript': chat_history})

async def fetch_conversation_transcript(conversation_id):
    """
    Fetch the conversation transcript from the ElevenLabs API using the conversation_id.
    """
    try:
        client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))
        transcript = client.conversational_ai.get_transcript(conversation_id)
        return transcript
    except Exception as e:
        logger.error(f"Error fetching conversation transcript: {e}")
        raise e

async def grade_conversation(conversation_id):
    """
    Grade the conversation using the LLM and save the grade to the database.
    """
    try:
        # Fetch the conversation transcript from ElevenLabs
        transcript = await fetch_conversation_transcript(conversation_id)

        # Grade the conversation using the LLM
        grading_result = await grade_with_llm(transcript)

        # Save the grade to the database
        await save_grade_to_db(conversation_id, grading_result)

        return grading_result
    except Exception as e:
        logger.error(f"Error grading conversation: {e}")
        raise e

async def grade_with_llm(transcript):
    """
    Grade the conversation using the LLM (Groq).
    """
    try:
        # Use the existing grading logic from app/utils/grading.py
        from .utils.grading import grade_conversation as llm_grade_conversation
        return llm_grade_conversation(transcript)
    except Exception as e:
        logger.error(f"Error grading with LLM: {e}")
        raise e

async def save_grade_to_db(conversation_id, grading_result, current_user):
    """
    Save the grading result to the database.
    """
    try:
        grade = Grade(
            conversation_id=conversation_id,
            final_score=grading_result.final_score,
            individual_scores=grading_result.individual_scores,
            performance_summary=grading_result.performance_summary,
            user_id=current_user,
            timestamp=datetime.utcnow()
        )
        await grade.insert()
        logger.info(f"Grade for conversation {conversation_id} saved to database.")
    except Exception as e:
        logger.error(f"Error saving grade to database: {e}")
        raise e

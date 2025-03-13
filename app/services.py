from .models import CaseStudy, ConversationLog, User, Session, Grade
import os
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from datetime import datetime
import logging
from flask import jsonify, request, g
from .utils.logger import logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
AGENT_ID = os.getenv('AGENT_ID')
API_KEY = os.getenv('ELEVENLABS_API_KEY')

# Global variables
conversation = None
chat_history = []

# Store chat messages
async def store_message(sender, message):
    chat_history.append({'sender': sender, 'message': message})
    # Update the current session with the latest message
    if g.get('current_session'):
        g.current_session.transcript = chat_history
        await g.current_session.save()

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
    signed_url = client.conversational_ai.get_signed_url(agent_id=AGENT_ID)
    return jsonify({"status": "success", "signed_url": signed_url.signed_url})

# Create user function
async def create_user(email):
    user = User(email=email, name="", role="student", date_added=datetime.utcnow(), date_updated=datetime.utcnow())
    await user.save_to_db()
    return user

async def get_user_by_email(email):
    return await User.find_by_email(email)

# API Endpoints
async def start_conversation():
    global conversation, chat_history
    try:
        # Check for JWT token to get current user
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            # Extract user info from token (implement JWT verification logic)
            user_email = extract_email_from_token(token)
        else:
            # For development/testing without authentication
            user_email = "test@example.com"
            
        # Initialize the conversation
        conversation = initialize_conversation()
        conversation.start_session()
        conv_id = conversation._conversation_id
        
        # Clear previous chat history
        chat_history = []
        
        # Create and store a new session in the database
        user = await get_user_by_email(user_email)
        if not user:
            user = await create_user(user_email)
            
        # End any existing active sessions for this user
        active_session = await Session.find_active_by_email(user_email)
        if active_session:
            await Session.end_session(active_session.id)
        
        # Create a new session
        new_session = Session(
            user_email=user_email,
            conversation_id=conv_id,
            is_active=True,
            start_time=datetime.utcnow(),
            transcript=[]
        )
        await new_session.insert()
        
        # Store the session in g for this request context
        g.current_session = new_session
        
        logger.info(f"Conversation started with ID: {conv_id} for user: {user_email}")
        return jsonify({'status': 'success', 'conversation_id': conv_id})
    except Exception as e:
        logger.error(f"Error starting conversation: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

async def stop_conversation():
    global conversation, chat_history
    try:
        if conversation:
            # Get conversation details before stopping
            conversation_id = conversation._conversation_id
            
            # Get current user from request
            auth_header = request.headers.get('Authorization')
            user_email = "test@example.com"  # Default for development
            
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                user_email = extract_email_from_token(token)
            
            # Stop the conversation
            conversation.end_session()
            logger.info(f"Conversation {conversation_id} ended")
            
            # Find and update the active session
            session = await Session.find_active_by_email(user_email)
            if session:
                # Update the transcript one last time
                session.transcript = chat_history
                # End the session
                await Session.end_session(session.id)
                
                # Save conversation to ConversationLog for historical record
                await save_conversation_to_db(conversation_id, chat_history, user_email)
                
                # Grade the conversation
                grading_result = await grade_conversation(conversation_id, user_email)
                
                # Clear the globals
                conversation = None
                chat_history = []
                
                return jsonify({
                    'status': 'success', 
                    'message': 'Conversation stopped and graded.',
                    'conversation_id': conversation_id,
                    'grading_result': grading_result
                })
            else:
                return jsonify({"status": "error", "message": "No active session found."}), 400
        else:
            return jsonify({"status": "error", "message": "No active conversation to stop."}), 400
    except Exception as e:
        logger.error(f"Error stopping conversation: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

async def save_conversation_to_db(conversation_id, transcript, user_email):
    """
    Save the conversation transcript and metadata to MongoDB.
    """
    try:
        # Find the user
        user = await User.find_by_email(user_email)
        if not user:
            user = await create_user(user_email)
        
        conversation_log = ConversationLog(
            user=user,
            conversation_id=conversation_id,
            transcript=transcript,
            timestamp=datetime.utcnow()
        )
        await conversation_log.insert()
        logger.info(f"Conversation {conversation_id} saved to database for user {user_email}.")
    except Exception as e:
        logger.error(f"Error saving conversation to database: {e}")
        raise e

def get_transcript():
    return jsonify({'transcript': chat_history})

async def fetch_conversation_transcript(conversation_id):
    """
    Fetch the conversation transcript from the database or ElevenLabs API.
    """
    try:
        # First try to get from our database
        conversation_log = await ConversationLog.find_one(
            ConversationLog.conversation_id == conversation_id
        )
        
        if conversation_log and conversation_log.transcript:
            return conversation_log.transcript
        
        # If not found in DB, fetch from ElevenLabs API
        client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))
        transcript = client.conversational_ai.get_conversation_transcript(conversation_id)
        return transcript
    except Exception as e:
        logger.error(f"Error fetching conversation transcript: {e}")
        raise e

async def grade_conversation(conversation_id, user_email):
    """
    Grade the conversation using the LLM and save the grade to the database.
    """
    try:
        # Fetch the conversation transcript
        transcript = await fetch_conversation_transcript(conversation_id)
        
        # Get the user
        user = await User.find_by_email(user_email)
        if not user:
            raise Exception(f"User not found: {user_email}")
            
        # Grade the conversation using the LLM
        from .utils.grading import grade_conversation as llm_grade_conversation
        grading_result = llm_grade_conversation(transcript)
        
        # Save the grade to the database
        await save_grade_to_db(conversation_id, grading_result, user)
        
        return grading_result
    except Exception as e:
        logger.error(f"Error grading conversation: {e}")
        raise e

async def save_grade_to_db(conversation_id, grading_result, user):
    """
    Save the grading result to the database.
    """
    try:
        # Find the case study if it exists (optional)
        case_study = await CaseStudy.find_one(CaseStudy.conversation_id == conversation_id)
        
        grade = Grade(
            user=user,
            case_study=case_study if case_study else None,
            final_score=grading_result.final_score,
            individual_scores=grading_result.individual_scores,
            performance_summary=grading_result.performance_summary,
            conversation_id=conversation_id,
            timestamp=datetime.utcnow()
        )
        await grade.insert()
        logger.info(f"Grade for conversation {conversation_id} saved to database for user {user.email}.")
        return grade
    except Exception as e:
        logger.error(f"Error saving grade to database: {e}")
        raise e

# Helper function to extract email from JWT token
def extract_email_from_token(token):
    """
    Extract user email from JWT token.
    Implement proper JWT verification logic here.
    """
    try:
        # This is a placeholder. Use your JWT library to properly decode and verify the token
        import jwt
        decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
        return decoded.get('email')
    except Exception as e:
        logger.error(f"Error extracting email from token: {e}")
        return "test@example.com"  # Fallback for development
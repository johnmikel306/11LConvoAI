# from app.services import get_transcript
import json
from .models import CaseStudy, ConversationLog, User, Session, Grade
import os
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from .models import User
from datetime import datetime, timezone
from .models import ConversationLog, Grade

from flask import jsonify
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
def store_message(sender, message):
    chat_history.append({'sender': sender, 'message': message})
    # Update the current session with the latest message
    if g.get('current_session'):
        g.current_session.transcript = chat_history
        g.current_session.save()

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
    try:
        logger.info(f"Attempting to create user with email: {email}")
        existing_user = await User.find_by_email(email)
        if existing_user:
            logger.info(f"User with email {email} already exists.")
            return existing_user

        user = User(email=email, name="", role="student", date_added=datetime.now(timezone.utc), date_updated=datetime.now(timezone.utc))
        await user.save_to_db()
        logger.info(f"User with email {email} created successfully.")
        return user
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise e
    
def get_user_by_email(email):
    return User.find_by_email(email)

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
        user = get_user_by_email(user_email)
        if not user:
            user = await create_user(user_email)
            
        # End any existing active sessions for this user
        active_session = Session.find_active_by_email(user_email)
        if active_session:
            Session.end_session(active_session.id)
        
        # Create a new session
        new_session = Session(
            user_email=user_email,
            conversation_id=conv_id,
            is_active=True,
            start_time=datetime.now(timezone.utc),
            transcript=[]
        )
        new_session.insert()
        
        # Store the session in g for this request context
        g.current_session = new_session
        
        logger.info(f"Conversation started with ID: {conv_id} for user: {user_email}")
        return jsonify({'status': 'success', 'conversation_id': conv_id})
    except Exception as e:
        logger.error(f"Error starting conversation: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def stop_conversation():
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
            session = Session.find_active_by_email(user_email)
            if session:
                # Update the transcript one last time
                session.transcript = chat_history
                # End the session
                Session.end_session(session.id)
                
                # Save conversation to ConversationLog for historical record
                save_conversation_to_db(conversation_id, chat_history, user_email)
                
                # Grade the conversation
                grading_result = grade_conversation(conversation_id, user_email)
                
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
        user = User.find_by_email(user_email)
        if not user:
            user = await create_user(user_email)
        
        conversation_log = ConversationLog(
            user=user,
            conversation_id=conversation_id,
            transcript=transcript,
            timestamp=datetime.now(timezone.utc)
        )
        conversation_log.insert()
        logger.info(f"Conversation {conversation_id} saved to database for user {user_email}.")
    except Exception as e:
        logger.error(f"Error saving conversation to database: {e}")
        raise e

def get_transcript():
    return jsonify({'transcript': chat_history})

def fetch_conversation_transcript(conversation_id):
    """
    Fetch the conversation transcript from the database or ElevenLabs API.
    """
  
    client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))
    transcript = client.conversational_ai.get_conversation(conversation_id).transcript
    trans = []
    for t in transcript:
        trans.append({"role": t.role, "message": t.message})
      
        
   
    return str(trans)
   

def grade_conversation(conversation_id, user_email):
    """
    Grade the conversation using the LLM and save the grade to the database.
    """
    # try:
    # Fetch the conversation transcript
    transcript = fetch_conversation_transcript(conversation_id)
    
    
    # Grade the conversation using the LLM
    from .utils.grading import grade_conversation as llm_grade_conversation
    grading_result = llm_grade_conversation(transcript, conversation_id)
    
    # Save the grade to the database
    save_grade_to_db(conversation_id, grading_result, user_email)
    
    return grading_result
    # except Exception as e:
    #     logger.error(f"Error grading conversation: {e}")
    #     raise e

async def save_grade_to_db(conversation_id, grading_result, user_email):
    """
    Save the grading result to the database.
    """
    try:
        # Find the case study if it exists (optional)
        case_study = await CaseStudy.find_one(CaseStudy.conversation_id == conversation_id)

        # Get the user object
        user = await User.find_by_email(user_email)  # Assuming this is where the user coroutine came from

        grade = Grade(
            user=user,
            case_study=case_study,  # No need for the conditional here, None is fine
            final_score=grading_result.final_score,
            individual_scores=grading_result.individual_scores,
            performance_summary=grading_result.performance_summary,
            timestamp=datetime.now(timezone.utc)
        )
        grade.insert()
        logger.info(f"Grade for conversation {conversation_id} saved to database for user {user.email}.")
       
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
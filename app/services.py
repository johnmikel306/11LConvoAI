from .models import CaseStudy, ConversationLog, User, Session, Grade
import os
from elevenlabs.client import ElevenLabs
from .models import User
from datetime import datetime, timezone

from flask import jsonify
import logging
from flask import jsonify, request, g
from .utils.logger import logger
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
AGENT_ID = os.getenv('AGENT_ID')
API_KEY = os.getenv('ELEVENLABS_API_KEY')

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
        logger.info(f"Attempting to create user with email: {str(email)}")  # Ensure email is a string
        existing_user = await User.find_by_email(str(email))  # Ensure email is a string

        if existing_user:
            logger.info(f"User with email {str(email)} already exists.")  # Ensure email is a string
            return existing_user

        user = User(
            email=str(email),  # Ensure email is a string
            name=str(email.split('@')[0]),  # Extract name from email and return as string
            role="student",
            date_added=datetime.now(timezone.utc),
            date_updated=datetime.now(timezone.utc)
        )
        await user.insert()  # Directly use insert instead of save_to_db
        logger.info(f"User with email {str(email)} created successfully.")  # Ensure email is a string
        return user
    
    except Exception as e:
        logger.error(f"Error creating user {email}: {str(e)}", exc_info=True)
        raise e
    
def create_user_sync(email):
    """
    Synchronous wrapper for create_user using asyncio
    """
    try:
        return asyncio.run(create_user(email))  # Use asyncio.run to run the async create_user function
    except Exception as e:
        logger.error(f"Error creating user {email}: {str(e)}")
        raise e
    
async def get_user_by_email(email):
    return await User.find_by_email(email)

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
        return None  # Fallback for development
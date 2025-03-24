from dotenv import load_dotenv
from .models import CaseStudy, ConversationLog, User, Session, Grade
import os
from elevenlabs.client import ElevenLabs
from .models import User
from datetime import datetime, timezone

from flask import jsonify
import logging

from .utils.logger import logger


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


AGENT_ID = os.getenv('AGENT_ID')
API_KEY = os.getenv('ELEVENLABS_API_KEY')

def get_signed_url():
    if not AGENT_ID:
        logger.error("AGENT_ID environment variable must be set")
        raise Exception("AGENT_ID environment variable must be set")
    client = ElevenLabs(api_key=API_KEY)
    signed_url = client.conversational_ai.get_signed_url(agent_id=AGENT_ID)
    return jsonify({"status": "success", "signed_url": signed_url.signed_url})


def create_user(email):

    existing_user = User.find_by_email(str(email))

    if existing_user:
        logger.info(f"User with email {str(email)} already exists.") 
        return existing_user

    user = User(
        email=str(email), 
        name=str(email.split('@')[0]),
        role="student",
        date_added=datetime.now(timezone.utc),
        date_updated=datetime.now(timezone.utc)
    )
    user.save() 
    return user
    


def extract_email_from_token(token):
    """
    Extract user email from JWT token.
    Implement proper JWT verification logic here.
    """
    try:
       
        import jwt
        decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
        return decoded.get('email')
    except Exception as e:
        logger.error(f"Error extracting email from token: {e}")
        return None
import jwt
from .models import CaseStudy, ConversationLog, User, Session, Grade
import os
from elevenlabs.client import ElevenLabs
from datetime import datetime, timezone
from fastapi import HTTPException
from .utils.logger import logger
import asyncio

AGENT_ID = os.getenv('AGENT_ID')
API_KEY = os.getenv('ELEVENLABS_API_KEY')

def get_signed_url():
    if not AGENT_ID:
        logger.error("AGENT_ID environment variable must be set")
        raise HTTPException(status_code=500, detail="AGENT_ID environment variable must be set")
    client = ElevenLabs(api_key=API_KEY)
    signed_url = client.conversational_ai.get_signed_url(agent_id=AGENT_ID)
    return {"status": "success", "signed_url": signed_url.signed_url}

async def create_user(email):
    try:
        logger.info(f"Attempting to create user with email: {str(email)}")
        existing_user = await User.find_by_email(str(email))
        
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
        await user.insert()
        logger.info(f"User with email {str(email)} created successfully.")
        return user
    except Exception as e:
        logger.error(f"Error creating user {email}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

def create_user_sync(email):
    try:
        return asyncio.run(create_user(email))
    except Exception as e:
        logger.error(f"Error creating user {email}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_user_by_email(email):
    return await User.find_by_email(email)

def extract_email_from_token(token):
    try:
        decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
        return decoded.get('email')
    except Exception as e:
        logger.error(f"Error extracting email from token: {e}")
        return None
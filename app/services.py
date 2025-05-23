# services.py

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

from .models import CaseStudy, UserRole
from .models import User
from .utils.auth import hash_password
from .utils.logger import logger

load_dotenv()

AGENT_ID = os.getenv('AGENT_ID')
API_KEY = os.getenv('ELEVENLABS_API_KEY')


# def get_signed_url():
#     if not AGENT_ID:
#         logger.error("AGENT_ID environment variable must be set")
#         raise Exception("AGENT_ID environment variable must be set")
#     client = ElevenLabs(api_key=API_KEY)
#     signed_url = client.conversational_ai.get_signed_url(agent_id=AGENT_ID)
#     return jsonify({"status": "success", "signed_url": signed_url.signed_url})

def get_signed_url_with_case_study(case_study_id=None):
    """Get a signed URL from ElevenLabs API, optionally using a specific case study's agent ID"""

    agent_id = os.getenv('AGENT_ID')

    if case_study_id:
        case_study = CaseStudy.objects(id=case_study_id).first()
        if case_study and case_study.agent_id:
            agent_id = case_study.agent_id

    if not agent_id:
        logger.error("No agent ID available")
        raise Exception("No agent ID available")

    client = ElevenLabs(api_key=API_KEY)
    signed_url = client.conversational_ai.get_signed_url(agent_id=agent_id)

    return signed_url.signed_url


def create_user(email, password=None, name=None, role=UserRole.STUDENT, **kwargs):
    existing_user = User.find_by_email(str(email))

    hashed_password = hash_password(str(password)) if password else None

    if existing_user:
        logger.info(f"User with email {str(email)} already exists.")
        return existing_user

    user = User(
        email=str(email),
        name=str(email.split('@')[0]) if not name else str(name),
        role=role,
        password=hashed_password,
        date_added=datetime.now(timezone.utc),
        date_updated=datetime.now(timezone.utc),
        **kwargs
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

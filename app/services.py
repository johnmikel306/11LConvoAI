# services.py

import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from .models import User
from .models import UserRole
from .utils.auth import hash_password
from .utils.logger import logger

load_dotenv()


def create_user(email, password=None, name=None, role=UserRole.STUDENT, **kwargs):
    existing_user = User.find_by_email(str(email))

    if existing_user:
        logger.info(f"User with email {str(email)} already exists.")
        # update user's name
        if name is not None:
            existing_user.name = name

        existing_user.save()
        return existing_user

    hashed_password = hash_password(str(password)) if password else None
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

# app/utils/auth.py
import bcrypt

def hash_password(password: str) -> str:
    """
    Hash the password using a secure hashing algorithm.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def check_password(hashed_password: str, password: str) -> bool:
    """
    Check if the provided password matches the hashed password.
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

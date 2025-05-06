from app.models import User
from ..utils.logger import logger
from functools import wraps
import os

from flask import jsonify, request, g
import jwt
from contextlib import contextmanager

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):        
        AUTH_HEADER = 'Authorization'
        token = None
      
        if AUTH_HEADER in request.headers:
            token = request.headers[AUTH_HEADER]
      
        if not token:
            return jsonify({'message' : 'Token is missing!'}), 401
  
        if token.startswith('Bearer '):
            token = token.replace('Bearer ', '', 1)
       
  
        data = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
        email = data.get('email')
        if not email:
            return jsonify({'message': 'Email not found in token'}), 401
        
        user = User.find_by_email(email) 
        
        if not user:
            return jsonify({'message' : 'User not found!'}), 401
        
    
        request.current_user = user
        logger.info(f"User {user.email} is authenticated")
        with token_data_context(user):
            return f( *args, **kwargs)
        
    return decorated



@contextmanager
def token_data_context(user):
    try:
        g.data = user
        yield
    finally:
        del g.data
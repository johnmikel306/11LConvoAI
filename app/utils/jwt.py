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
  
        # try:
        if token.startswith('Bearer '):
            token = token.replace('Bearer ', '', 1)
       
        print("Token: \n", token)
        data = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
        email = data.get('email')
        if not email:
            return jsonify({'message': 'Email not found in token'}), 401
        print("Data: \n", data) 
        print("Data: \n", email)   
        user = User.find_by_email(email) 
        
        # if not user:
        #     return jsonify({'message' : 'User not found!'}), 401
        
    
        request.current_user = user
        logger.info(f"User {user.email} is authenticated")
        # except jwt.ExpiredSignatureError:
        #     return jsonify({'message': 'Token has expired!'}), 401
        # except jwt.InvalidTokenError:
        #     return jsonify({'message': 'Token is invalid!'}), 401
        # except Exception as e:
        #     logger.error(f"An error occur validating the token : {str(e)}")
        #     return jsonify({
        #         'message': 'Token is invalid!'
        #     }), 401
        # # returns the current logged in users context to the routes
        with token_data_context(user):
            return f( *args, **kwargs)
        
    return decorated



@contextmanager
def token_data_context(user_info):
    try:
        g.data = user_info
        yield
    finally:
        del g.data
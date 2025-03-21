# decorator for verifying the JWT
from ..utils.logger import logger
from functools import wraps
import os
from ..services import get_user_by_email
from flask import jsonify, request
import jwt


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):        
        AUTH_HEADER = 'Authorization'
        token = None
        # jwt is passed in the request header
        if AUTH_HEADER in request.headers:
            token = request.headers[AUTH_HEADER]
        # return 401 if token is not passed
        if not token:
            return jsonify({'message' : 'Token is missing!'}), 401
  
        # try:
        # decoding the payload to fetch the stored details
        print("Token: \n", token)
        data = jwt.decode(token, os.getenv('JWT_SECRET'))
        email = data.get('email')
        if not email:
            return jsonify({'message': 'Email not found in token'}), 401
        print("Data: \n", data) 
        print("Data: \n", email)   
        user = get_user_by_email(email)  
        if not user:
            return jsonify({'message' : 'User not found!'}), 401
        
        #store the user in the request context
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
        return  f(*args, **kwargs)
        
    return decorated
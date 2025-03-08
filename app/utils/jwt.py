
# decorator for verifying the JWT
from functools import wraps
import os
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
  
        try:
            # decoding the payload to fetch the stored details
            data = jwt.decode(token, os.getenv('JWT_SECRET'))
             # Fetch the user details using the email from DB and store in current_user
        except:
            return jsonify({
                'message' : 'Token is invalid!'
            }), 401
        # returns the current logged in users context to the routes
        return  f(*args, **kwargs)
  
    return decorated
import datetime
from flask import jsonify, render_template, redirect, url_for, request, session
import jwt
from .utils.cas_helper import validate_service_ticket
import os
from .services import start_conversation, stop_conversation, get_transcript, get_signed_url_endpoint
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_routes(app):
    @app.route('/')
    def index():
        logger.info("Rendering index page")
        return render_template('index.html')
    
    @app.route('/start', methods=['POST'])
    def start():
        logger.info("Start conversation endpoint called")
        return start_conversation()

    @app.route('/stop', methods=['POST'])
    def stop():
        logger.info("Stop conversation endpoint called")
        return stop_conversation()

    @app.route('/transcript', methods=['GET'])
    def transcript():
        logger.info("Transcript endpoint called")
        return get_transcript()
     
    @app.route('/get_signed_url', methods=['GET'])
    def signed_url():
        logger.info("Get signed URL endpoint called")
        return get_signed_url_endpoint()

    # CAS Login Route
    @app.route('/cas/auth-url', methods=['GET'])
    def cas_login():
        # Redirect to CAS login page
        service_url = url_for('cas_validate', _external=True)
        cas_login_url = f"{os.getenv('CAS_LOGIN_URL')}?service={service_url}"
        logger.info(f"Redirecting to CAS login: {cas_login_url}")
        return jsonify({'url': cas_login_url})

    # CAS Validation Route
    @app.route('/cas/validate', methods=['POST'])
    def cas_validate():
        # Get the Service Ticket (ST) from the query parameters
        ticket = request.form['ticket']
        if not ticket:
            logger.error("Invalid request: No ticket provided.")
            return "Invalid request: No ticket provided."

        # Validate the Service Ticket
        service_url = url_for('cas_validate', _external=True)
        user_email = validate_service_ticket(ticket, service_url)

        if user_email:
            # Save the user to DB

            token = jwt.encode({
                'email': user_email,
                'exp' : datetime.utcnow() + datetime.timedelta(days=7)
            }, os.getenv('JWT_SECRET'))
            
            return jsonify({'token': token.decode('UTF-8')})
        else:
            logger.error("Failed to validate CAS ticket.")
            return jsonify({ "error": "Failed to validate ticket. Please try again." })

    # CAS Logout Route
    @app.route('/cas/logout')
    def cas_logout():
        # Clear the session
        session.pop('user', None)
        logger.info("User logged out.")
        return redirect(url_for('index'))


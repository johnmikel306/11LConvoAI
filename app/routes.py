import datetime
import jwt
from flask import jsonify, render_template, redirect, url_for, request, session
from .utils.grading import grade_conversation
from .utils.jwt import token_required
from .utils.cas_helper import validate_service_ticket
import os
from .services import create_user, get_transcript, start_conversation, stop_conversation, get_signed_url, grade_conversation, conversation
from .utils.logger import logger

def init_routes(app):
    @app.route('/')
    def index():
        logger.info("Rendering index page")
        return render_template('index.html')
    
    @app.route('/start', methods=['POST'])
    # @token_required
    def start():
        try:
            logger.info("Start conversation endpoint called")
            return start_conversation()
        except Exception as e:
            logger.error(f"Error in /start: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
            
    @app.route('/stop', methods=['POST'])
    # @token_required
    def stop():
        try:
            logger.info("Stop conversation endpoint called")
            
            # Check if there's an active conversation
            if not conversation or not conversation._conversation_id:
                return jsonify({
                    "status": "error",
                    "message": "No active conversation to stop"
                }), 400

            # Get conversation ID before stopping
            conversation_id = conversation._conversation_id
            
            # Stop the conversation
            stop_conversation()
            logger.info(f"Conversation {conversation_id} stopped")

            # Grade the conversation
            grading_result = grade_conversation(conversation_id)
            logger.info(f"Conversation {conversation_id} graded")

            return jsonify({
                "status": "success",
                "message": "Conversation stopped and graded",
                "conversation_id": conversation_id,
                "grading_result": grading_result
            })

        except Exception as e:
            logger.error(f"Error in /stop: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/transcript', methods=['GET'])
    # @token_required
    def transcript():
        try:
            logger.info("Transcript endpoint called")
            return get_transcript()
        except Exception as e:
            logger.error(f"Error in /transcript: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
     
    @app.route('/get_signed_url', methods=['GET'])
    def signed_url():
        try:
            logger.info("Get signed URL endpoint called")
            return get_signed_url()
        except Exception as e:
            logger.error(f"Error in /get_signed_url: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # CAS Login Route
    @app.route('/cas/auth-url', methods=['GET'])
    def cas_login():
        try:
            # Redirect to CAS login page
            service_url = "https://miva-mind.vercel.app/auth/cas/callback"
            cas_login_url = f"{os.getenv('CAS_LOGIN_URL')}?service={service_url}"
            logger.info(f"Redirecting to CAS login: {cas_login_url}")
            return jsonify({'url': cas_login_url})
        except Exception as e:
            logger.error(f"Error in /cas/auth-url: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # CAS Validation Route
    @app.route('/cas/validate', methods=['POST'])
    def cas_validate():
        try:
            # Get the Service Ticket (ST) from the query parameters
            ticket = request.form['ticket']
            if not ticket:
                logger.error("Invalid request: No ticket provided.")
                return jsonify({"status": "error", "message": "No ticket provided."}), 400

            # Validate the Service Ticket
            service_url = "https://miva-mind.vercel.app/auth/cas/callback"
            user_email = validate_service_ticket(ticket, service_url)

            if user_email:
                # Save the user to DB
                try:
                    create_user(user_email)  # Call create_user to save the user
                except Exception as e:
                    logger.error(f"Failed to create user: {e}")
                    return jsonify({"status": "error", "message": "Failed to create user."}), 500

                token = jwt.encode({
                    'email': user_email,
                    'exp' : datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
                }, os.getenv('JWT_SECRET'))   

                return jsonify({'token': token.decode('UTF-8')})

            else:
                logger.error("Failed to validate CAS ticket.")
                return jsonify({"status": "error", "message": "Failed to validate ticket."}), 401
        except Exception as e:
            logger.error(f"Error in /cas/validate: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # CAS Logout Route
    @app.route('/cas/logout')
    def cas_logout():
        try:
            # Clear the session
            if 'user' in session:
                session.pop('user', None)
                logger.info("User logged out.")
                return redirect(url_for('index')), jsonify({"status": "success", "message": "User logged out."})
            else:
                logger.info("No user in session.")
                return jsonify({"status": "error", "message": "No user in session."}), 400
        except Exception as e:
            logger.error(f"Error in /cas/logout: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
        
    @app.route('/grade/<conversation_id>', methods=['POST'])
    # @token_required
    async def grade_conversation_endpoint(conversation_id):
        try:
            logger.info(f"Grading conversation {conversation_id}")

            # Grade the conversation
            grading_result = await grade_conversation(conversation_id)

            return jsonify({
                "status": "success",
                "message": "Conversation graded.",
                "grading_result": grading_result
            })
        except Exception as e:
            logger.error(f"Error grading conversation: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500


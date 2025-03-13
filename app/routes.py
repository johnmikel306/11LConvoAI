import datetime
import jwt
from flask import jsonify, render_template, redirect, url_for, request, session, g
from .utils.grading import grade_conversation
from .utils.jwt import token_required
from .utils.cas_helper import validate_service_ticket
import os
from .services import create_user, get_transcript, start_conversation, stop_conversation, get_signed_url, grade_conversation
from .utils.logger import logger
from .models import Grade, Session, User

def init_routes(app):
    # Request middleware to set current session in g
    @app.before_request
    async def load_session():
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                # Extract email from token
                decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
                user_email = decoded.get('email')
                
                # Find active session for this user
                active_session = await Session.find_active_by_email(user_email)
                g.current_session = active_session
            except Exception as e:
                logger.error(f"Error loading session: {e}")
                g.current_session = None
        else:
            g.current_session = None

    @app.route('/')
    def index():
        logger.info("Rendering index page")
        return render_template('index.html')
    
    @app.route('/start', methods=['POST'])
    # @token_required
    async def start():
        try:
            logger.info("Start conversation endpoint called")
            return await start_conversation()
        except Exception as e:
            logger.error(f"Error in /start: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
            
    @app.route('/stop', methods=['POST'])
    # @token_required
    async def stop():
        try:
            logger.info("Stop conversation endpoint called")
            return await stop_conversation()
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
            service_url = url_for('cas_validate', _external=True)
            cas_login_url = f"{os.getenv('CAS_LOGIN_URL')}?service={service_url}"
            logger.info(f"Redirecting to CAS login: {cas_login_url}")
            return jsonify({'url': cas_login_url})
        except Exception as e:
            logger.error(f"Error in /cas/auth-url: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
        # CAS Validation Route (continued)
    @app.route('/cas/validate', methods=['POST'])
    async def cas_validate():
        try:
            # Get the Service Ticket (ST) from the query parameters
            ticket = request.form['ticket']
            if not ticket:
                logger.error("Invalid request: No ticket provided.")
                return jsonify({"status": "error", "message": "No ticket provided."}), 400

            # Validate the Service Ticket
            service_url = url_for('cas_validate', _external=True)
            user_email = validate_service_ticket(ticket, service_url)

            if user_email:
                # Save the user to DB
                try:
                    user = await create_user(user_email)
                except Exception as e:
                    logger.error(f"Failed to create user: {e}")
                    return jsonify({"status": "error", "message": "Failed to create user."}), 500

                # End any active sessions for this user
                active_session = await Session.find_active_by_email(user_email)
                if active_session:
                    await Session.end_session(active_session.id)

                # Create JWT token
                token = jwt.encode({
                    'email': user_email,
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
                }, os.getenv('JWT_SECRET'))   

                return jsonify({'token': token})
            else:
                logger.error("Failed to validate CAS ticket.")
                return jsonify({"status": "error", "message": "Failed to validate ticket."}), 401
        except Exception as e:
            logger.error(f"Error in /cas/validate: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # CAS Logout Route
    @app.route('/cas/logout')
    async def cas_logout():
        try:
            # Get the current user email from JWT token
            auth_header = request.headers.get('Authorization')
            user_email = None
            
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
                user_email = decoded.get('email')
            
            if user_email:
                # End any active sessions for this user
                active_session = await Session.find_active_by_email(user_email)
                if active_session:
                    await Session.end_session(active_session.id)
                
                logger.info(f"User {user_email} logged out.")
                return jsonify({"status": "success", "message": "User logged out."})
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
            
            # Get the current user email from JWT token
            auth_header = request.headers.get('Authorization')
            user_email = "test@example.com"  # Default for development
            
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
                user_email = decoded.get('email')

            # Grade the conversation
            grading_result = await grade_conversation(conversation_id, user_email)

            return jsonify({
                "status": "success",
                "message": "Conversation graded.",
                "grading_result": grading_result
            })
        except Exception as e:
            logger.error(f"Error grading conversation: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
            
    # New endpoint to get user's sessions
    @app.route('/sessions', methods=['GET'])
    # @token_required
    async def get_user_sessions():
        try:
            # Get the current user email from JWT token
            auth_header = request.headers.get('Authorization')
            user_email = None
            
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
                user_email = decoded.get('email')
            
            if not user_email:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401
                
            # Find all sessions for this user
            sessions = await Session.find(Session.user_email == user_email).to_list()
            
            # Format sessions for response
            formatted_sessions = []
            for session in sessions:
                formatted_sessions.append({
                    "id": str(session.id),
                    "conversation_id": session.conversation_id,
                    "start_time": session.start_time.isoformat(),
                    "end_time": session.end_time.isoformat() if session.end_time else None,
                    "is_active": session.is_active,
                    "transcript_length": len(session.transcript) if session.transcript else 0
                })
                
            return jsonify({
                "status": "success",
                "sessions": formatted_sessions
            })
        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
            
    # New endpoint to get grades for a user
    @app.route('/grades', methods=['GET'])
    # @token_required
    async def get_user_grades():
        try:
            # Get the current user email from JWT token
            auth_header = request.headers.get('Authorization')
            user_email = None
            
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
                user_email = decoded.get('email')
            
            if not user_email:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401
                
            # Find the user
            user = await User.find_by_email(user_email)
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404
                
            # Find all grades for this user
            grades = await Grade.find(Grade.user.id == user.id).to_list()
            
            # Format grades for response
            formatted_grades = []
            for grade in grades:
                formatted_grades.append({
                    "id": str(grade.id),
                    "conversation_id": grade.conversation_id,
                    "timestamp": grade.timestamp.isoformat(),
                    "final_score": grade.final_score,
                    "individual_scores": grade.individual_scores,
                    "performance_summary": grade.performance_summary
                })
                
            return jsonify({
                "status": "success",
                "grades": formatted_grades
            })
        except Exception as e:
            logger.error(f"Error getting user grades: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
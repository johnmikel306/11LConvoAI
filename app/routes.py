import datetime
from .utils.grading import grade_conversation
from app.utils.jwt import token_required
from app.utils import jwt
from flask import jsonify, render_template, redirect, url_for, request, session, g
from .utils.jwt import token_required
from .utils.cas_helper import validate_service_ticket
import os
from .services import create_user, create_user_sync, get_signed_url, grade_conversation
from .utils.logger import logger
from .models import Grade, Session, User
import eventlet
from beanie.exceptions import DocumentNotFound



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
                logger.error(f"Error loading session: {str(e)}")
                g.current_session = None
        else:
            g.current_session = None

    @app.route('/')
    def index():
        logger.info("Rendering index page")
        return render_template('index.html')
     
    @app.route('/get_signed_url', methods=['GET'])
    def signed_url():
        try:
            logger.info("Get signed URL endpoint called")
            return get_signed_url()
        except Exception as e:
            logger.error(f"Error in /get_signed_url: {str(e)}")
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
            logger.error(f"Error in /cas/auth-url: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
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
            logger.info(f"Validating ticket: {ticket} with service URL: {service_url}")
            user_email = validate_service_ticket(ticket, service_url)

            if not user_email:
                return jsonify({"status": "error", "message": "Invalid ticket"}), 401

            # Create or fetch the user
            try:
                # Use create_user_sync to handle the async create_user function
                user = create_user_sync(user_email)
            except Exception as e:
                logger.error(f"Failed to find/create user: {user_email}. Error: {str(e)}")
                return jsonify({"status": "error", "message": "User creation failed"}), 500

            # Create a JWT token
            token = jwt.encode({
                'email': user_email,
                'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
            }, os.getenv('JWT_SECRET'))

            return jsonify({'token': token})
        except Exception as e:
            logger.error(f"Error in /cas/validate: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # CAS Logout Route
    @app.route('/cas/logout')
    def cas_logout():
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
                active_session = Session.find_active_by_email(user_email)
                if active_session:
                    Session.end_session(active_session.id)
                
                logger.info(f"User {user_email} logged out.")
                return jsonify({"status": "success", "message": "User logged out."})
            else:
                logger.info("No user in session.")
                return jsonify({"status": "error", "message": "No user in session."}), 400
        except Exception as e:
            logger.error(f"Error in /cas/logout: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
        
    @app.route('/grade/<conversation_id>', methods=['POST'])
    async def grade_conversation_endpoint(conversation_id):
        try:
           # Get the current user email from the session
            if not g.current_session:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401
        
            user_email = g.current_session.user_email
            
            # Grade the conversation
            grading_result = await grade_conversation(conversation_id, user_email)
            
            return jsonify({
                "status": "success",
                "message": "Conversation graded.",
                "grading_result": grading_result
            })
        except Exception as e:
            logger.error(f"Error grading conversation: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # New endpoint to get user's sessions
    @app.route('/sessions', methods=['GET'])
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
            logger.error(f"Error getting user sessions: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
            
    # New endpoint to get grades for a user
    @app.route('/grades', methods=['GET'])
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
            logger.error(f"Error getting user grades: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
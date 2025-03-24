import datetime

from dotenv import load_dotenv
from .utils.grading import grade_conversation
from app.utils.jwt import token_required
import jwt
from flask import jsonify, render_template, request, g
from .utils.cas_helper import validate_service_ticket
import os
from .services import create_user, get_signed_url
from .utils.logger import logger
from .models import Grade, Session, User


load_dotenv()

def init_routes(app):
    
    @app.before_request
    def load_session():
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
             
                decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
                user_email = decoded.get('email')
                
            
                active_session = Session.find_active_by_email(user_email)
                g.user_info = active_session
            except Exception as e:
                logger.error(f"Error loading session: {str(e)}")
                g.user_info = None
        else:
            g.user_info = None

    @app.route('/')
    def index():
        logger.info("Rendering index page")
        return render_template('index.html')
     
    @app.route('/get_signed_url', methods=['GET'])
    def signed_url():
       
        logger.info("Get signed URL endpoint called")
        url = get_signed_url()
        return url
       
    @app.route('/cas/auth-url', methods=['GET'])
    def cas_login():
      
        service_url = "https://miva-mind.vercel.app/auth/cas/callback"
        cas_login_url = f"{os.getenv('CAS_LOGIN_URL')}?service={service_url}"
        
        return jsonify({'url': cas_login_url})
      
    @app.route('/cas/validate', methods=['POST'])
    def cas_validate():
       
        ticket = request.form['ticket']
        if not ticket:
            logger.error("Invalid request: No ticket provided.")
            return jsonify({"status": "error", "message": "No ticket provided."}), 400

        
        service_url = "https://miva-mind.vercel.app/auth/cas/callback"
        logger.info(f"Validating ticket: {ticket} with service URL: {service_url}")
        user_email = validate_service_ticket(ticket, service_url)
        
        if not user_email:
            return jsonify({"status": "error", "message": "Invalid ticket"}), 401

        
        create_user(user_email)
        print(user_email)
        token = jwt.encode({
            'email': user_email,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
        }, os.getenv('JWT_SECRET'), algorithm='HS256')
        print(token)
        return jsonify({'token': token})
    
 
    @app.route('/cas/logout')
    def cas_logout():
        
        auth_header = request.headers.get('Authorization')
        user_email = None
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
            user_email = decoded.get('email')
        

        if user_email:
            
            active_session = Session.find_active_by_email(user_email)
            if active_session:
                Session.end_session(active_session.id)
            
            logger.info(f"User {user_email} logged out.")
            return jsonify({"status": "success", "message": "User logged out."})
        else:
            logger.info("No user in session.")
            return jsonify({"status": "error", "message": "No user in session."}), 400
    
    @app.route('/grade/<conversation_id>', methods=['POST'])
    # @token_required
    def grade_conversation_endpoint(conversation_id):

        # if not g.data:
        #     return jsonify({"status": "error", "message": "User not authenticated"}), 401
        user_email = "alaminibrahim433@gmail.com"
        # user_email = g.data.email
        grading_result = grade_conversation(conversation_id, user_email)
        
        return jsonify({
            "status": "success",
            "message": "Conversation graded.",
            "grading_result": str(grading_result)
        })
   
        
    @app.route('/grades', methods=['GET'])
    def get_user_grades():
       
        auth_header = request.headers.get('Authorization')
        user_email = None
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
            user_email = decoded.get('email')
        
        if not user_email:
            return jsonify({"status": "error", "message": "User not authenticated"}), 401
        
        user = User.find_by_email(user_email)
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
            
        grades = Grade.find(Grade.user.id == user.id).to_list()
        
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
    

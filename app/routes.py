import datetime

from dotenv import load_dotenv

from elevenlabs import ElevenLabs
from .utils.grading import grade_conversation
from app.utils.jwt import token_required
import jwt
from flask import jsonify, render_template, request, g
from .utils.cas_helper import validate_service_ticket
import os
from .services import create_user
from .utils.logger import logger
from .models import CaseStudy, ConversationLog, Grade, Session, User

load_dotenv()

API_KEY = os.getenv('ELEVENLABS_API_KEY')


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

    # @app.route('/get_signed_url', methods=['GET'])
    # def signed_url():

    #     logger.info("Get signed URL endpoint called")
    #     url = get_signed_url()
    #     return url

    @app.route('/get_signed_url', methods=['GET'])
    @token_required
    def signed_url():
        """Get a signed URL for the ElevenLabs API with optional case study selection"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Check if a case study ID was provided
            case_study_id = request.args.get('case_study_id')

            # Default agent ID from environment variable
            agent_id = os.getenv('AGENT_ID')
            case_study = None

            # If a case study ID is provided, use its agent ID instead
            if case_study_id:
                case_study = CaseStudy.objects(id=case_study_id).first()
                if case_study and case_study.agent_id:
                    agent_id = case_study.agent_id

            if not agent_id:
                logger.error("No agent ID available")
                return jsonify({
                    "status": "error",
                    "message": "No agent ID available"
                }), 400

            # Create or update the user's session with the case study information
            user_email = g.data.email
            active_session = Session.find_active_by_email(user_email)

            if active_session:
                # Update existing session with new conversation
                active_session.case_study_id = case_study_id if case_study_id else None
                active_session.last_activity = datetime.datetime.now(datetime.timezone.utc)
                active_session.save()
            else:
                # Create new session
                session = Session(
                    user_email=user_email,
                    case_study_id=case_study_id if case_study_id else None,
                    is_active=True,
                    start_time=datetime.datetime.now(datetime.timezone.utc),
                    last_activity=datetime.datetime.now(datetime.timezone.utc)
                )
                session.save()

            # Get the signed URL using the agent_id
            client = ElevenLabs(api_key=API_KEY)
            signed_url = client.conversational_ai.get_signed_url(agent_id=agent_id)

            response_data = {
                "status": "success",
                "signed_url": signed_url.signed_url
            }

            # Include case study information if available
            if case_study:
                response_data["case_study"] = {
                    "id": str(case_study.id),
                    "title": case_study.title
                }

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error in get_signed_url: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while generating the signed URL"
            }), 500

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

    # @app.route('/grade/<conversation_id>', methods=['POST'])
    # @token_required
    # def grade_conversation_endpoint(conversation_id):

    #     if not g.data:
    #         return jsonify({"status": "error", "message": "User not authenticated"}), 401
    #     try:
    #         user_email = g.data.email
    #         # user_email = "alamin@gmaill.com"
    #         grading_result = grade_conversation(conversation_id, user_email)

    #         return jsonify({
    #             "status": "success",
    #             "message": "Conversation graded.",
    #             "grading_result": str(grading_result)
    #         })
    #     except:
    #         return jsonify({"status": "failed", "message": "error on the server"}), 500

    @app.route('/grade/<conversation_id>', methods=['POST'])
    @token_required
    def grade_conversation_endpoint(conversation_id):
        if not g.data:
            return jsonify({"status": "error", "message": "User not authenticated"}), 401

        try:
            user_email = g.data.email

            # Find the active session to get the case study information
            active_session = Session.find_active_by_email(user_email)
            case_study_id = active_session.case_study_id if active_session else None
            case_study = None

            # If we have a case study ID, get the case study
            if case_study_id:
                case_study = CaseStudy.objects(id=case_study_id).first()

            # Grade the conversation, passing the case study if available
            grading_result = grade_conversation(conversation_id, user_email, case_study)

            return jsonify({
                "status": "success",
                "message": "Conversation graded.",
                "grading_result": str(grading_result)
            })
        except Exception as e:
            logger.error(f"Error in grade_conversation_endpoint: {str(e)}")
            return jsonify({
                "status": "failed",
                "message": "Error on the server"
            }), 500

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
        try:
            user = User.find_by_email(user_email)
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404

            grades = Grade.find_grade_by_user_email(user_email)

            formatted_grades = []
            for grade in grades:
                formatted_performance_summary = {}
                for key, items in grade.performance_summary.items():
                    formatted_items = []
                    for item in items:
                        formatted_items.append({
                            "title": item.title,
                            "description": item.description
                        })
                    formatted_performance_summary[key] = formatted_items

                formatted_grades.append({
                    "id": str(grade.id),
                    "user_email": grade.user.email,
                    "timestamp": grade.timestamp.isoformat(),
                    "final_score": grade.final_score,
                    "individual_scores": grade.individual_scores,
                    "performance_summary": formatted_performance_summary,
                    "conversation_id": grade.conversation_id
                })

            return jsonify({
                "status": "success",
                "grades": formatted_grades
            })
        except:
            return jsonify({
                "status": "failed",
                "message": "failed to retrieve responses"
            }), 500

    @app.route('/get_conversation_count', methods=['GET'])
    @token_required
    def get_conversation_count():
        try:
            if not g.data:
                return jsonify({
                    "status": "error",
                    "message": "User not authenticated"
                }), 401

            user_email = g.data.email

            user = User.find_by_email(user_email)
            conversation_count = ConversationLog.objects(user=user).count()
            return jsonify({
                "status": "success",
                "conversation_count": conversation_count
            })

        except Exception as e:

            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching the conversation count"
            }), 500

    @app.route('/download_report', methods=['GET'])
    @token_required
    def download_report():
        try:
            if not g.data:
                return jsonify({
                    "status": "error",
                    "message": "User not authenticated"
                }), 401

            user_email = g.data.email
            user = User.find_by_email(user_email)
            grade = Grade.find_grade_by_user_email(user_email).order_by('-timestamp').first()

            if not grade:
                return jsonify({
                    "status": "error",
                    "message": "No grade report found"
                }), 404

            performance_summary = {
                key: [{"title": item.title, "description": item.description} for item in items]
                for key, items in grade.performance_summary.items()
            }

            case_study = {
                "id": str(grade.case_study.id) if grade.case_study else None,
                "title": grade.case_study.title if grade.case_study else None,
            }

            return jsonify({
                "status": "success",
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name
                },
                "session_id": str(grade.conversation_id),
                "timestamp": grade.timestamp.isoformat(),
                "case_study": case_study,
                "report": {
                    "overall_summary": "Your performance was fair, demonstrating some understanding of the task but lacking in critical thinking and comprehension. Your communication skills were clear, but the response was limited in scope.",
                    "final_score": grade.final_score,
                    "individual_scores": grade.individual_scores,
                    "performance_summary": performance_summary
                }
            })
        except Exception as e:
            logger.error(f"Error in /download_report: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching the conversation count"
            }), 500

    @app.route('/view_previous_grades', methods=['GET'])
    @token_required
    def view_previous_grades():
        try:
            if not g.data:
                return jsonify({
                    "status": "error",
                    "message": "User not authenticated"
                }), 401

            user_email = g.data.email
            user = User.find_by_email(user_email)
            grades = Grade.find_grade_by_user_email(user_email)

            if not grades:
                return jsonify({
                    "status": "error",
                    "message": "No grades found"
                }), 404

            formatted_grades = []
            for grade in grades:
                performance_summary = {
                    key: [{"title": item.title, "description": item.description} for item in items]
                    for key, items in grade.performance_summary.items()
                }

                formatted_grades.append({
                    "overall_summary": "Your performance was fair, demonstrating some understanding of the task but lacking in critical thinking and comprehension. Your communication skills were clear, but the response was limited in scope.",
                    "final_score": grade.final_score,
                    "individual_scores": grade.individual_scores,
                    "performance_summary": performance_summary
                })

            return jsonify({
                "status": "success",
                "conversation_count": grades.count(),
                "report": formatted_grades
            })
        except Exception as e:
            logger.error(f"Error in /view_previous_grades: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching the conversation count"
            }), 500

    @app.route('/case-studies', methods=['GET'])
    @token_required
    def get_case_studies():
        """Get all available case studies"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Get all case studies from the database
            case_studies = CaseStudy.objects.all()

            # Format the case studies data
            formatted_case_studies = []
            for case in case_studies:
                formatted_case_studies.append({
                    "id": str(case.id),
                    "title": case.title,
                    "description": case.description,
                    "agentID": case.agent_id
                })

            return jsonify({
                "status": "success",
                "case_studies": formatted_case_studies
            })

        except Exception as e:
            logger.error(f"Error in /case-studies: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching case studies"
            }), 500

    @app.route('/case-studies/<case_study_id>', methods=['GET'])
    @token_required
    def get_case_study(case_study_id):
        """Get a specific case study by ID"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Find the case study by ID
            case_study = CaseStudy.objects(id=case_study_id).first()

            if not case_study:
                return jsonify({
                    "status": "error",
                    "message": "Case study not found"
                }), 404

            # Format the case study data
            formatted_case = {
                "id": str(case_study.id),
                "title": case_study.title,
                "description": case_study.description
            }

            return jsonify({
                "status": "success",
                "case_study": formatted_case
            })

        except Exception as e:
            logger.error(f"Error in /case-studies/{case_study_id}: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching the case study"
            }), 500

    @app.route('/admin/case-studies', methods=['POST'])
    @token_required
    def create_case_study():
        """Create a new case study (admin/faculty only)"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Check if user has admin/faculty role
            user_email = g.data.email
            user = User.find_by_email(user_email)

            if not user or user.role not in ['admin', 'faculty']:
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized access. Admin or faculty role required."
                }), 403

            # Get data from request
            data = request.json
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No data provided"
                }), 400

            # Validate required fields
            if 'title' not in data or 'description' not in data:
                return jsonify({
                    "status": "error",
                    "message": "Title and description are required"
                }), 400

            # Create new case study
            case_study = CaseStudy(
                title=data['title'],
                description=data['description'],
                agent_id=data.get('agent_id')  # Optional field
            )
            case_study.save()

            return jsonify({
                "status": "success",
                "message": "Case study created successfully",
                "case_study": {
                    "id": str(case_study.id),
                    "title": case_study.title,
                    "description": case_study.description,
                    "agent_id": case_study.agent_id
                }
            }), 201

        except Exception as e:
            logger.error(f"Error in create_case_study: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while creating the case study"
            }), 500

    @app.route('/admin/case-studies/<case_study_id>', methods=['PUT'])
    @token_required
    def update_case_study(case_study_id):
        """Update an existing case study (admin/faculty only)"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            user_email = g.data.email
            user = User.find_by_email(user_email)

            if not user or user.role not in ['admin', 'faculty']:
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized access. Admin or faculty role required."
                }), 403

            case_study = CaseStudy.objects(id=case_study_id).first()

            if not case_study:
                return jsonify({
                    "status": "error",
                    "message": "Case study not found"
                }), 404

            # Get data from request
            data = request.json
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No data provided"
                }), 400

            # Update case study fields
            if 'title' in data:
                case_study.title = data['title']
            if 'description' in data:
                case_study.description = data['description']
            if 'agent_id' in data:
                case_study.agent_id = data['agent_id']

            case_study.save()

            return jsonify({
                "status": "success",
                "message": "Case study updated successfully",
                "case_study": {
                    "id": str(case_study.id),
                    "title": case_study.title,
                    "description": case_study.description,
                    "agent_id": case_study.agent_id
                }
            })

        except Exception as e:
            logger.error(f"Error in update_case_study: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while updating the case study"
            }), 500

    @app.route('/admin/case-studies/<case_study_id>', methods=['DELETE'])
    @token_required
    def delete_case_study(case_study_id):
        """Delete a case study (admin/faculty only)"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Check if user has admin/faculty role
            user_email = g.data.email
            user = User.find_by_email(user_email)

            if not user or user.role not in ['admin', 'faculty']:
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized access. Admin or faculty role required."
                }), 403

            # Find the case study by ID
            case_study = CaseStudy.objects(id=case_study_id).first()

            if not case_study:
                return jsonify({
                    "status": "error",
                    "message": "Case study not found"
                }), 404

            # Delete the case study
            case_study.delete()

            return jsonify({
                "status": "success",
                "message": "Case study deleted successfully"
            })

        except Exception as e:
            logger.error(f"Error in delete_case_study: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while deleting the case study"
            }), 500

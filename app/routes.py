import datetime
import os

import jwt
from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from flask import jsonify, render_template, request, g

from app.utils.jwt import token_required
from .models import CaseStudy, ConversationLog, Grade, Session, User, UserRole
from .services import create_user
from .utils.auth import check_password, hash_password
from .utils.cas_helper import validate_service_ticket
from .utils.grading import grade_conversation
from .utils.logger import logger

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

        service_url = os.getenv('CAS_SERVICE_URL')
        cas_login_url = f"{os.getenv('CAS_LOGIN_URL')}?service={service_url}"

        return jsonify({'url': cas_login_url})

    @app.route('/cas/validate', methods=['POST'])
    def cas_validate():

        ticket = request.form['ticket']
        if not ticket:
            logger.error("Invalid request: No ticket provided.")
            return jsonify({"status": "error", "message": "No ticket provided."}), 400

        service_url = os.getenv('CAS_SERVICE_URL')
        logger.info(f"Validating ticket: {ticket} with service URL: {service_url}")
        user_email = validate_service_ticket(ticket, service_url)

        if not user_email:
            return jsonify({"status": "error", "message": "Invalid ticket"}), 401

        create_user(user_email)
        token = jwt.encode({
            'email': user_email,
            'role': 'student',
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
        }, os.getenv('JWT_SECRET'), algorithm='HS256')
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

    @app.route('/auth/register', methods=['POST'])
    def register():
        """Register a new user"""
        try:
            # Get the user email and password from the request
            data = request.json()
            if not data or 'email' not in data or not data['password']:
                return jsonify({"status": "error", "message": "Email and password are required"}), 400
            user_email = data['email']
            user_password = data['password']
            user_name = data.get('name', None)
            # Check if the user already exists
            existing_user = User.find_by_email(user_email)
            if existing_user:
                return jsonify({"status": "error", "message": "User already exists"}), 409
            # Create a new user
            create_user(user_email, user_password, user_name, UserRole.FACULTY)
            return jsonify({"status": "success", "message": "User registered successfully"}), 201
        except Exception as e:
            logger.error(f"Error in register: {str(e)}")
            return jsonify({"status": "error", "message": "An error occurred during registration"}), 500

    @app.route('/auth/login', methods=['POST'])
    def login():
        """Login endpoint for user authentication"""
        try:
            # Get the user email and password from the request
            data = request.json()
            if not data or 'email' not in data or not data['password']:
                return jsonify({"status": "error", "message": "Wrong email/password"}), 400
            user_email = data['email']
            user_password = data['password']
            # Validate the user email
            user = User.find_by_email(user_email)
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404
            # Check if the password is correct
            if not check_password(user.password, user_password):
                return jsonify({"status": "error", "message": "Wrong email/password"}), 401
            # Create a JWT token for the user
            token = jwt.encode({
                'email': user_email,
                'role': user.role,
                'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
            }, os.getenv('JWT_SECRET'), algorithm='HS256')

            return jsonify({"status": "success", "message": "User logged in.", token: token})
        except Exception as e:
            logger.error(f"Error in login: {str(e)}")
            return jsonify({"status": "error", "message": "An error occurred during login"}), 500

    @app.route('/auth/change-password', methods=['POST'])
    def change_password():
        """Change user password"""
        try:
            # Get the user email and new password from the request
            data = request.json()
            if not data or 'email' not in data or not data['new_password'] or not data['old_password']:
                return jsonify({"status": "error", "message": "Email, old and new password are required"}), 400
            user_email = data['email']
            new_password = data['new_password']
            old_password = data['old_password']
            # Find the user by email
            user = User.find_by_email(user_email)
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404

            # Check if the old password is correct
            if not check_password(user.password, old_password):
                return jsonify({"status": "error", "message": "Wrong old password"}), 401

            # Check if the new password is the same as the old password
            if check_password(user.password, new_password):
                return jsonify(
                    {"status": "error", "message": "New password cannot be the same as the old password"}), 400

            # Hash the new password
            new_password = hash_password(new_password)

            # Update the user's password
            user.password = new_password
            user.save()
            return jsonify({"status": "success", "message": "Password changed successfully"}), 200
        except Exception as e:
            logger.error(f"Error in change_password: {str(e)}")
            return jsonify({"status": "error", "message": "An error occurred during password change"}), 500

    @app.route('/users/<user_id>', methods=['GET'])
    @token_required
    def get_user(user_id):
        """Get user information by ID"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Find the user by ID
            user = User.objects(id=user_id).first()

            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404

            # Format the user data
            formatted_user = {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "title": user.title,
                "department": user.department,
                "date_added": user.date_added.isoformat(),
                "date_updated": user.date_updated.isoformat()
            }

            return jsonify({
                "status": "success",
                "user": formatted_user
            })

        except Exception as e:
            logger.error(f"Error in get_user: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching the user"
            }), 500

    @app.route('/users/<user_id>', methods=['PUT'])
    @token_required
    def update_user(user_id):
        """Update user information by ID"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Find the user by ID
            user = User.objects(id=user_id).first()

            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404

            # Get data from request
            data = request.json
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            # Update user fields
            if 'name' in data:
                user.name = data['name']
            if 'title' in data:
                user.title = data['title']
            if 'department' in data:
                user.department = data['department']

            user.save()

            return jsonify({
                "status": "success",
                "message": "User updated successfully",
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "role": user.role,
                    "title": user.title,
                    "department": user.department,
                    "date_added": user.date_added.isoformat(),
                    "date_updated": user.date_updated.isoformat()
                }
            })

        except Exception as e:
            logger.error(f"Error in update_user: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while updating the user"
            }), 500

    @app.route('/students', methods=['GET'])
    @token_required
    def get_students():
        """Get all students"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Get pagination parameters
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 10))

            # Get filter parameters
            filter_assessment_date_range = request.args.get('assessment_date')
            filter_case_study_id = request.args.get('case_study_id')

            # Get all students from the database
            # WARNING: we are not paginating the students here because we are not adding the filters
            # to the query. This means that if we have a lot of students, this could be a performance issue.
            students = User.objects(role=UserRole.STUDENT)

            # Format the student data
            formatted_students = []
            for student in students:
                # Get session information for each student
                student_session = Session.find_active_by_email(student.email)

                # Get grading information for each student
                student_grades = Grade.find_grades_by_user_email(student.email)

                # Filter grades by assessment date range if provided
                if filter_assessment_date_range:
                    start_date, end_date = filter_assessment_date_range.split(',')
                    student_grades_with_assessment_date_filter = [grade for grade in student_grades if
                                                                  start_date <= grade.timestamp <= end_date]
                    if len(student_grades_with_assessment_date_filter) == 0:
                        # Skip this student if no grades match the assessment date filter
                        continue

                # Filter students by case study ID if provided
                if filter_case_study_id:
                    student_grades_with_case_study_filter = [grade for grade in student_grades if
                                                             str(grade.case_study.id) == filter_case_study_id]
                    if len(student_grades_with_case_study_filter) == 0:
                        # Skip this student if no grades match the case study filter
                        continue

                # Calculate average score
                average_score = 0
                if student_grades:
                    total_score = sum(grade.final_score for grade in student_grades)
                    average_score = total_score / len(student_grades)

                formatted_students.append({
                    "id": str(student.id),
                    "email": student.email,
                    "name": student.name,
                    "role": student.role,
                    "title": student.title,
                    "department": student.department,
                    "last_assessment_date": student_session.last_activity.isoformat() if student_session else None,
                    "sessions_completed": len(student_grades),
                    "average_score": average_score,
                })

            # Paginate the results
            start = (page - 1) * per_page
            end = start + per_page
            paginated_students = formatted_students[start:end]

            return jsonify({
                "status": "success",
                "data": paginated_students,
                "meta": {
                    "page": page,
                    "per_page": per_page,
                    "total": len(formatted_students),
                }
            })

        except Exception as e:
            logger.error(f"Error in get_students: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching students"
            }), 500

    @app.route('/students/<student_id>', methods=['GET'])
    @token_required
    def get_student(student_id):
        """Get a specific student by ID"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Find the student by ID
            student = User.objects(id=student_id).first()

            if not student:
                return jsonify({"status": "error", "message": "Student not found"}), 404

            # Get grades for the student grouped by case study
            student_grades = Grade.objects.aggregate(
                {
                    "$group": {
                        "_id": "$case_study",
                        "grades": {
                            "$push": {
                                "final_score": "$final_score",
                                "timestamp": "$timestamp"
                            }
                        },
                    }
                }
            )

            # Format the student data
            formatted_student = {
                "id": str(student.id),
                "email": student.email,
                "name": student.name,
                "role": student.role,
                "title": student.title,
                "sessions_count": Session.objects(user_email=student.email).count(),
                "case_studies_count": len(student_grades),
                "grades": [
                    {
                        "case_study_id": str(grade["_id"]),
                        "grades": grade["grades"]
                    } for grade in student_grades
                ],
                "department": student.department,
            }

            return jsonify({
                "status": "success",
                "student": formatted_student
            })

        except Exception as e:
            logger.error(f"Error in get_student: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching the student"
            }), 500

    @app.route('/students/<student_id>/grades', methods=['GET'])
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

            # Grading means a session is completed
            active_session = Session.find_active_by_email(user_email)
            if active_session:
                Session.end_session(active_session.id)

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

            case_study_id = request.args.get('case_study_id')

            case_study = CaseStudy.objects(id=case_study_id).first() if case_study_id else None

            conversation_count = ConversationLog.objects(user=user, case_study=case_study).count()
            return jsonify({
                "status": "success",
                "case_study_id": case_study_id,
                "conversation_count": conversation_count
            })

        except Exception as e:
            logger.error(f"Error in get_conversation_count: {str(e)}")
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
            case_study_id = request.args.get('case_study_id')
            grades = Grade.find_grade_by_user_email(user_email, case_study_id).order_by('-timestamp')
            reports = []
            if not grades or len(grades) == 0:
                return jsonify({
                    "status": "error",
                    "message": "No grade report found"
                }), 404

            case_study = {
                "id": str(grades[0].case_study.id) if grades[0].case_study else None,
                "title": grades[0].case_study.title if grades[0].case_study else None,
            }

            for grade in grades:
                performance_summary = {
                    key: [{"title": item.title, "description": item.description} for item in items]
                    for key, items in grade.performance_summary.items()
                }

                reports.append({
                    "overall_summary": grade.overall_summary if grade.overall_summary else "Your performance was fair, demonstrating some understanding of the task but lacking in critical thinking and comprehension. Your communication skills were clear, but the response was limited in scope.",
                    "final_score": grade.final_score,
                    "individual_scores": grade.individual_scores,
                    "performance_summary": performance_summary,
                })

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
                "reports": reports,
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

            case_study_id = request.args.get('case_study_id')

            user_email = g.data.email
            user = User.find_by_email(user_email)
            grades = Grade.find_grade_by_user_email(user_email, case_study_id)

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
                    "overall_summary": grade.overall_summary if grade.overall_summary else "Your performance was fair, demonstrating some understanding of the task but lacking in critical thinking and comprehension. Your communication skills were clear, but the response was limited in scope.",
                    "final_score": grade.final_score,
                    "individual_scores": grade.individual_scores,
                    "performance_summary": performance_summary
                })

            return jsonify({
                "status": "success",
                "case_study_id": case_study_id,
                "conversation_count": grades.count(),
                "grades": formatted_grades
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

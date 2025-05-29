import datetime
import os

import jwt
from bson import ObjectId
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
from .utils.perser import remove_none

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
            if not data or 'email' not in data or not data['newPassword'] or not data['oldPassword']:
                return jsonify({"status": "error", "message": "Email, old and new password are required"}), 400
            user_email = data['email']
            new_password = data['newPassword']
            old_password = data['oldPassword']
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

            auth_user_id = g.data.id

            # Find the user by ID
            user = User.objects(id=auth_user_id if user_id == 'me' else user_id).first()

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

            auth_user_id = g.data.id

            # Find the user by ID
            user = User.objects(id=auth_user_id if user_id == 'me' else user_id).first()

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
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            case_study_id = request.args.get('case_study_id')

            assessment_date_filter_pipeline = [
                {
                    "$match": {
                        "$expr": {
                            "$and": [
                                {"$gte": ["$grades.last_assessment_date", datetime.datetime.fromisoformat(start_date)]},
                                {"$lte": ["$grades.last_assessment_date", datetime.datetime.fromisoformat(end_date)]}
                            ]
                        }
                    }
                }
            ] if start_date and end_date else []

            case_study_id_filter_pipeline = [
                {
                    "$match": {
                        "$expr": {
                            "$eq": ["$grades.case_study", ObjectId(case_study_id)]
                        }
                    }
                }
            ] if case_study_id else []

            pagination_pipeline = [
                {
                    "$skip": (page - 1) * per_page
                },
                {
                    "$limit": per_page
                }
            ] if per_page > 0 and page > 0 else []

            pipeline = [
                {
                    "$lookup": {
                        "from": "grades",
                        "let": {"userId": "$_id"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {
                                        "$eq": ["$user", "$$userId"]
                                    }
                                }
                            },
                            {
                                "$group": {
                                    "_id": "$user",
                                    "average_score": {"$avg": "$final_score"},
                                    "last_assessment_date": {"$max": "$timestamp"},
                                    "total_sessions": {"$sum": 1},
                                    "case_study": {"$first": "$case_study"},
                                }
                            }
                        ],
                        "as": "grades"
                    }
                },
                {
                    "$unwind": {
                        "path": "$grades",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                *assessment_date_filter_pipeline,
                *case_study_id_filter_pipeline,
                *pagination_pipeline,
                {
                    "$project": {
                        "_id": 0,
                        "id": "$_id",
                        "email": 1,
                        "name": 1,
                        "role": 1,
                        "title": 1,
                        "department": 1,
                        "last_assessment_date": "$grades.last_assessment_date",
                        "total_sessions": "$grades.total_sessions",
                        "average_score": "$grades.average_score"
                    }
                }
            ]

            # Get all students from the database
            # WARNING: we are not paginating the students here because we are not adding the filters
            # to the query. This means that if we have a lot of students, this could be a performance issue.
            students = User.objects(role=UserRole.STUDENT).aggregate(pipeline)

            # Format the student data
            formatted_students = []
            for student in students:
                formatted_students.append({
                    "id": str(student.get('id')),
                    "email": student.get('email'),
                    "name": student.get('name'),
                    "role": student.get('role'),
                    "title": student.get('title'),
                    "department": student.get('department'),
                    "lastAssessmentDate": student.get('last_assessment_date', None),
                    "sessionsCompleted": student.get('total_sessions', 0),
                    "averageScore": round(student.get('average_score', 0), 2) if student.get(
                        'average_score') is not None else 0
                })

            return jsonify({
                "status": "success",
                "data": formatted_students,
                "meta": {
                    "page": page,
                    "per_page": per_page,
                    "total": User.objects(role=UserRole.STUDENT).count(),
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

            grades = [
                {
                    "case_study_id": str(grade["_id"]),
                    "grades": grade["grades"]
                } for grade in student_grades
            ]

            # Format the student data
            formatted_student = {
                "id": str(student.id),
                "email": student.email,
                "name": student.name,
                "role": student.role,
                "title": student.title,
                "sessions_count": Session.objects(user_email=student.email).count(),
                "case_studies_count": len(grades),
                "grades": grades,
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

    @app.route('/metrics/aggregate', methods=['GET'])
    @token_required
    def get_metrics():
        """Get system metrics"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            case_study_id = request.args.get('case_study_id')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            case_study = CaseStudy.objects(id=case_study_id).first() if case_study_id else None

            filters = {
                'timestamp__gte': start_date,
                'timestamp__lte': end_date,
                'case_study': case_study
            }

            filters_sessions = {
                'case_study_id': case_study_id,
                'start_time__gte': start_date,
                'start_time__lte': end_date
            }

            total_case_studies_completed = Grade.objects(**remove_none(filters)).aggregate(
                {"$group": {"_id": "$case_study._id", "count": {"$sum": 1}}}
            )

            average_score = Grade.objects(**remove_none(filters)).average('final_score')
            total_conversations = ConversationLog.objects(**remove_none(filters)).count()
            total_sessions = Session.objects(**remove_none(filters_sessions)).count()
            total_grades = Grade.objects(**remove_none(filters)).count()

            metrics = {
                "total_students": User.objects(role=UserRole.STUDENT).count(),
                "total_case_studies": CaseStudy.objects.count(),
                "total_conversations": total_conversations,
                "total_sessions": total_sessions,
                "total_grades": total_grades,
                "average_score": round(average_score, 2) if average_score else 0,
                "total_case_studies_completed": sum(
                    item['count'] for item in total_case_studies_completed
                ) if total_case_studies_completed else 0,
            }

            return jsonify({
                "status": "success",
                "metrics": metrics
            })

        except Exception as e:
            logger.error(f"Error in /metrics/aggregate: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching metrics"
            }), 500

    @app.route('/metrics/grades', methods=['GET'])
    @token_required
    def get_timeseries_grades_metrics():
        """Get timeseries metrics for grades"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Get the start and end dates from the request
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            case_study_id = request.args.get('case_study_id')

            case_study = CaseStudy.objects(id=case_study_id).first() if case_study_id else None

            # Aggregate grades by date
            grades_metrics = Grade.objects(
                **remove_none({
                    'timestamp__gte': start_date,
                    'timestamp__lte': end_date,
                    'case_study': case_study
                })
            ).aggregate(
                {
                    "$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                        "communication_score": {"$avg": "$individual_scores.communication"},
                        "critical_thinking_score": {"$avg": "$individual_scores.critical_thinking"},
                        "comprehension_score": {"$avg": "$individual_scores.comprehension"},
                        "average_score": {"$avg": "$final_score"},
                        "total_grades": {"$sum": 1}
                    }
                },
                {
                    "$sort": {"_id": 1}
                }
            )

            formatted_metrics = []
            for metric in grades_metrics:
                formatted_metrics.append({
                    "date": metric['_id'],
                    "average_score": metric['average_score'],
                    "total_grades": metric['total_grades'],
                    "communication_score": metric['communication_score'],
                    "critical_thinking_score": metric['critical_thinking_score'],
                    "comprehension_score": metric['comprehension_score']
                })

            return jsonify({
                "status": "success",
                "grades_metrics": formatted_metrics
            })

        except Exception as e:
            logger.error(f"Error in /metrics/grades: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching grades metrics"
            }), 500

    @app.route('/students/<student_id>/activity-logs', methods=['GET'])
    @token_required
    def get_students_activity_logs(student_id):
        """Get student activity logs"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            # Get the student by ID
            student = User.objects(id=student_id).first() if student_id != 'all' else None

            case_study_id = request.args.get('case_study_id')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            case_study = CaseStudy.objects(id=case_study_id).first() if case_study_id else None

            filters = {
                'timestamp__gte': start_date,
                'timestamp__lte': end_date,
                'case_study': case_study,
                'user': student
            }

            # Get the activity logs for all users
            activity_logs = Grade.objects(
                **remove_none(filters)
            ).order_by('-timestamp').limit(5)

            formatted_logs = []
            for log in activity_logs:
                formatted_logs.append({
                    "timestamp": log.timestamp.isoformat(),
                    "title": f"{log.user.name} just completed '{log.case_study.title}'",
                })

            return jsonify({
                "status": "success",
                "logs": formatted_logs
            })

        except Exception as e:
            logger.error(f"Error in get_user_activity_logs: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching activity logs"
            }), 500

    @app.route('/students/<student_id>/case-studies', methods=['GET'])
    @token_required
    def get_student_case_studies(student_id):
        """Get case studies for a specific student"""
        try:
            if not g.data:
                return jsonify({"status": "error", "message": "User not authenticated"}), 401

            lean = int(request.args.get('lean', 0))

            # Find the student by ID
            student = User.objects(id=student_id).first()

            if not student:
                return jsonify({"status": "error", "message": "Student not found"}), 404

            # Get all case studies for the student
            grades = Grade.objects(user=student).aggregate(
                {
                    "$group": {
                        "_id": "$case_study._id",
                        "title": {"$first": "$case_study.title"},
                        "noOfAttempts": {"$sum": 1},
                        "averageScore": {"$avg": "$final_score"},
                    }
                }
            )

            # Format the case studies data
            formatted_case_studies = []
            for grade in grades:
                formatted_case_studies.append({
                    "id": str(grade.id),
                    "title": grade.title,
                    "timestamp": grade.get('timestamp', None),
                    "noOfAttempts": grade.get('noOfAttempts', 0),
                    "averageScore": round(grade.get('averageScore', 0), 2)
                })

            return jsonify({
                "status": "success",
                "case_studies": formatted_case_studies
            })

        except Exception as e:
            logger.error(f"Error in /students/{student_id}/case-studies: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An error occurred while fetching case studies"
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

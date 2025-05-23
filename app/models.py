# models.py

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List

from mongoengine import Document, StringField, DateTimeField, EmailField, ReferenceField, IntField, DictField, \
    ListField, BooleanField, EmbeddedDocument, EmbeddedDocumentField, EnumField
from pydantic import BaseModel, Field

from app.utils.auth import hash_password


class PerformanceItem(BaseModel):
    """
    Model for individual performance items (strengths/weaknesses).
    Example:
        PerformanceItem(title="Strong analytical skills", description="The student demonstrated excellent ability to analyze complex situations.")
    """
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)


class PerformanceItemDocument(EmbeddedDocument):
    title = StringField(required=True, max_length=200)
    description = StringField(required=True)


class UserRole(Enum):
    """
    Enum for user roles.
    """
    STUDENT = "student"
    FACULTY = "faculty"


class User(Document):
    name = StringField(required=True)
    email = EmailField(required=True, unique=True)
    role = EnumField(UserRole, default=UserRole.STUDENT)
    password = StringField(default=None, required=False)
    token = StringField(default=None, required=False)
    title = StringField(default=None, required=False)
    department = StringField(default=None, required=False)
    date_added = DateTimeField(default=datetime.now(timezone.utc))
    date_updated = DateTimeField()

    meta = {'collection': 'users'}

    @classmethod
    def find_by_email(cls, email: str) -> Optional["User"]:
        """
        Find a user by email in the database.
        """
        return cls.objects(email=email).first()

    @classmethod
    def create(cls, **kwargs) -> "User":
        """
        Create a new user and save it to the database.
        """
        # If password is provided, hash it
        if "password" in kwargs:
            kwargs["password"] = hash_password(kwargs["password"])
            pass
        user = cls(**kwargs)
        user.save()
        return user


class CaseStudy(Document):
    title = StringField(required=True)
    description = StringField(required=True)
    agent_id = StringField()

    meta = {'collection': 'case_studies'}


class Grade(Document):
    user = ReferenceField(User, required=True)
    case_study = ReferenceField(CaseStudy, required=False)
    overall_summary = StringField(required=True)
    final_score = IntField(required=True, min_value=0, max_value=100)
    individual_scores = DictField(required=True)
    performance_summary = DictField(field=ListField(EmbeddedDocumentField(PerformanceItemDocument)))
    conversation_id = StringField(required=True)
    timestamp = DateTimeField(default=datetime.now(timezone.utc))

    meta = {'collection': 'grades'}

    @classmethod
    def create_grade(
            cls,
            user: User,
            conversation_id: str,
            overall_summary: str,
            final_score: int,
            individual_scores: Dict[str, int],
            performance_summary: Dict[str, List[dict]],
            case_study: CaseStudy = None,
    ) -> "Grade":
        """
        Create and save a new grade entry.
        """

        processed_performance_summary = {}
        for key, items in performance_summary.items():
            processed_items = []
            for item in items:
                embedded_item = PerformanceItemDocument(
                    title=item["title"],
                    description=item["description"]
                )
                processed_items.append(embedded_item)
            processed_performance_summary[key] = processed_items

        grade = cls(
            user=user,
            case_study=case_study,
            conversation_id=conversation_id,
            overall_summary=overall_summary,
            final_score=final_score,
            individual_scores=individual_scores,
            performance_summary=processed_performance_summary,
            timestamp=datetime.now(timezone.utc)
        )
        grade.save()
        return grade

    @classmethod
    def find_by_conversation_id(cls, conversation_id: str) -> Optional["Grade"]:
        """
        Find a grade entry by conversation ID.
        """
        return cls.objects(conversation_id=conversation_id).first()

    @classmethod
    def find_grade_by_user_email(cls, user_email: str, case_study_id: Optional[str] = None) -> "Grade":
        # Find the user first
        user = User.objects(email=user_email).first()

        # If user is not found, return an empty queryset
        if not user:
            return cls.objects.none()

        # If case_study_id is provided, filter by it
        if case_study_id:
            case_study = CaseStudy.objects(id=case_study_id).first()
            if not case_study:
                return cls.objects(user=user)
            # Find all grades for the specific user and case study
            return cls.objects(user=user, case_study=case_study)

        # Find all grades for the specific user, populating the case study
        return cls.objects(user=user)

    @classmethod
    def find_grades_by_user_email(cls, user_email: str) -> List["Grade"]:
        """
        Find all grades for a specific user by email.
        """
        user = User.objects(email=user_email).first()
        if not user:
            return []
        return cls.objects(user=user)


class ConversationLog(Document):
    user = ReferenceField(User, required=True)
    conversation_id = StringField(required=True)
    case_study = ReferenceField(CaseStudy, required=False)  # New field to reference case study
    transcript = ListField(DictField())
    timestamp = DateTimeField(default=datetime.now(timezone.utc))

    meta = {'collection': 'conversation_logs'}

    @classmethod
    def create_log(
            cls,
            user: User,
            conversation_id: str,
            transcript: List[Dict],
            case_study: CaseStudy = None  # Add optional case_study parameter
    ) -> "ConversationLog":
        """
        Create and save a new conversation log entry.
        """
        log = cls(
            user=user,
            conversation_id=conversation_id,
            case_study=case_study,
            transcript=transcript,
            timestamp=datetime.now(timezone.utc)
        )
        log.save()
        return log


class Session(Document):
    user_email = StringField(required=True)
    conversation_id = StringField()
    case_study_id = StringField()  # New field to store case study ID
    is_active = BooleanField(default=True)
    start_time = DateTimeField(default=datetime.now(timezone.utc))
    end_time = DateTimeField()
    transcript = ListField(DictField(), default=[])
    last_activity = DateTimeField()

    meta = {'collection': 'sessions'}

    @classmethod
    def find_active_by_email(cls, email: str) -> Optional["Session"]:
        """
        Find an active session for a user by email.
        """
        return cls.objects(user_email=email, is_active=True).first()

    @classmethod
    def end_session(cls, session_id):
        """
        End a session.
        """
        session = cls.objects(id=session_id).first()
        if session:
            session.is_active = False
            session.end_time = datetime.now(timezone.utc)
            session.save()
            return session
        return None

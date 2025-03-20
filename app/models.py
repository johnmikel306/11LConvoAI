from datetime import datetime, timezone
from mongoengine import Document, StringField, DateTimeField, EmailField, ReferenceField, IntField, DictField, ListField, BooleanField, EmbeddedDocument, EmbeddedDocumentField, EmbeddedDocumentListField
from typing import Optional, Dict, List, ClassVar
from pydantic import BaseModel, Field, EmailStr


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

class User(Document):
    name = StringField(required=True)
    email = EmailField(required=True, unique=True)
    role = StringField(required=True)
    date_added = DateTimeField(default=datetime.now(timezone.utc))
    date_updated = DateTimeField()
    
    meta = {'collection': 'users'}

    @classmethod
    def find_by_email(cls, email: str) -> Optional["User"]:
        """
        Find a user by email in the database.
        """
        return cls.objects(email=email).first()
    
    def create(self, **kwargs) -> "User":
        """
        Create a new user and save it to the database.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.save()
        return self

class CaseStudy(Document): 
    title = StringField(required=True)
    description = StringField(required=True)
    agent_id = StringField()
    conversation_id = StringField()
    transcript = ListField(DictField())

    meta = {'collection': 'case_studies'}

class Grade(Document):
    user = ReferenceField(User, required=True)
    case_study = ReferenceField(CaseStudy, required=True)
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
        case_study: CaseStudy,
        conversation_id: str,
        final_score: int,
        individual_scores: Dict[str, int],
        performance_summary: Dict[str, List[dict]]
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

class ConversationLog(Document):
    user = ReferenceField(User, required=True)
    conversation_id = StringField(required=True)
    transcript = ListField(DictField())
    timestamp = DateTimeField(default=datetime.now(timezone.utc))

    meta = {'collection': 'conversation_logs'}

    @classmethod
    def create_log(
        cls,
        user: User,
        conversation_id: str,
        transcript: List[Dict]
    ) -> "ConversationLog":
        """
        Create and save a new conversation log entry.
        """
        log = cls(
            user=user,
            conversation_id=conversation_id,
            transcript=transcript,
            timestamp=datetime.now(timezone.utc)
        )
        log.save()
        return log

class Session(Document):
    user_email = StringField(required=True)
    conversation_id = StringField()
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
from datetime import datetime, timezone
from beanie import Document, PydanticObjectId
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, EmailStr

class PerformanceItem(BaseModel):
    """
    Model for individual performance items (strengths/weaknesses).
    Example:
        PerformanceItem(title="Strong analytical skills", description="The student demonstrated excellent ability to analyze complex situations.")
    """
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)

class User(Document):
    id: PydanticObjectId = None
    name: str
    email: EmailStr
    role: str
    date_added: Optional[datetime]
    date_updated: Optional[datetime]
    
    class Meta:
       collection = "users"  # Collection name in MongoDB

    @classmethod
    async def find_by_email(cls, email: str) -> Optional["User"]:
        """
        Find a user by email in the database.
        """
        return await cls.find_one({"email": email})
    
    async def create(self, **kwargs) -> "User":
        """
        Create a new user and save it to the database.
        """
        user = await self.insert(**kwargs)
        return user

class CaseStudy(Document): 
    title: str
    description: str
    agent_id: Optional[str]
    conversation_id: Optional[str]
    transcript: Optional[List[Dict]]  # Store the transcript here

    class Meta:
        collection = "case_studies"  # Collection name in MongoDB

class Grade(Document):
    user: User
    case_study: CaseStudy
    final_score: int = Field(..., ge=0, le=100)  # Ensure score is between 0-100
    individual_scores: Dict[str, int] = Field(...)  # e.g., {"Critical Thinking": 90, "Communication": 85}
    performance_summary: Dict[str, List[PerformanceItem]]  # Use PerformanceItem model for structured data
    conversation_id: str
    timestamp: datetime

    class Meta:
        collection = "grades"  # Collection name in MongoDB

    @classmethod
    async def create_grade(
        cls,
        user: User,
        case_study: CaseStudy,
        conversation_id: str,
        final_score: int,
        individual_scores: Dict[str, int],
        performance_summary: Dict[str, List[PerformanceItem]]
    ) -> "Grade":
        """
        Create and save a new grade entry.
        """
        grade = cls(
            user=user,
            case_study=case_study,
            conversation_id=conversation_id,
            final_score=final_score,
            individual_scores=individual_scores,
            performance_summary=performance_summary,
            timestamp=datetime.now(timezone.utc)
        )
        await grade.insert()
        return grade

    @classmethod
    async def find_by_conversation_id(cls, conversation_id: str) -> Optional["Grade"]:
        """
        Find a grade entry by conversation ID.
        """
        return await cls.find_one({"conversation_id": conversation_id})

class ConversationLog(Document):
    user: User
    conversation_id: str
    transcript: list  # List of chat messages
    timestamp: datetime

    class Meta:
        collection = "conversation_logs"  # Collection name in MongoDB

    @classmethod
    async def create_log(
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
        await log.insert()
        return log

class Session(Document):
    user_email: str
    conversation_id: Optional[str]
    is_active: bool = True
    start_time: datetime = datetime.now(timezone.utc)
    end_time: Optional[datetime] = None
    transcript: Optional[List[Dict]] = []
    last_activity: Optional[datetime] = None  # Timestamp of last activity in the session

    class Meta:
        collection = "sessions"  # Collection name in MongoDB

    @classmethod
    async def find_active_by_email(cls, email: str) -> Optional["Session"]:
        """
        Find an active session for a user by email.
        """
        return await cls.find_one({"user_email": email, "is_active": True})
    
    @classmethod
    async def end_session(cls, session_id: PydanticObjectId):
        """
        Asynchronously end a session.
        """
        session = await cls.get(session_id)
        if session:
            session.is_active = False
            session.end_time = datetime.now(timezone.utc)
            await session.save()
            return session
        return None
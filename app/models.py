from datetime import datetime, timezone
from beanie import Document, PydanticObjectId
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, EmailStr

class PerformanceItem(BaseModel):
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
       collection = "users"

    @classmethod
    async def find_by_email(cls, email: str) -> Optional["User"]:
        return await cls.find_one({"email": email})
    
    async def create(self, **kwargs) -> "User":
        user = await self.insert(**kwargs)
        return user

class CaseStudy(Document): 
    title: str
    description: str
    agent_id: Optional[str]
    conversation_id: Optional[str]
    transcript: Optional[List[Dict]]

    class Meta:
        collection = "case_studies"

class Grade(Document):
    user: User
    case_study: CaseStudy
    final_score: int = Field(..., ge=0, le=100)
    individual_scores: Dict[str, int] = Field(...)
    performance_summary: Dict[str, List[PerformanceItem]]
    conversation_id: str
    timestamp: datetime

    class Meta:
        collection = "grades"

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
        return await cls.find_one({"conversation_id": conversation_id})

class ConversationLog(Document):
    user: User
    conversation_id: str
    transcript: list
    timestamp: datetime

    class Meta:
        collection = "conversation_logs"

    @classmethod
    async def create_log(
        cls,
        user: User,
        conversation_id: str,
        transcript: List[Dict]
    ) -> "ConversationLog":
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
    last_activity: Optional[datetime] = None

    class Meta:
        collection = "sessions"

    @classmethod
    async def find_active_by_email(cls, email: str) -> Optional["Session"]:
        return await cls.find_one({"user_email": email, "is_active": True})
    
    @classmethod
    async def end_session(cls, session_id: PydanticObjectId):
        session = await cls.get(session_id)
        if session:
            session.is_active = False
            session.end_time = datetime.now(timezone.utc)
            await session.save()
            return session
        return None
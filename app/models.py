from datetime import datetime
from beanie import Document, PydanticObjectId
from typing import Optional
from pydantic import BaseModel
from typing import Dict, List

class User(Document):
    id: PydanticObjectId = None
    name: str
    email: str
    role: str
    date_added: Optional[datetime]
    date_updated: Optional[datetime]
    
    class Meta:
       collection = "users" # Collection name in MongoDB

    @classmethod
    async def find_by_email(cls, email: str) -> Optional["User"]:
        """
        Find a user by email in the database.
        """
        return await cls.find_one({cls.email == email})
    
    async def save_to_db(self):
        """
        Save the user to the database.
        """
        existing_user = await User.find_by_email(self.email)
        if existing_user:
            return None # User already exists
        
        await self.insert()
        return self
    
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
    final_score: int
    individual_scores: Dict[str, int]  # e.g., {"Critical Thinking": 90, "Communication": 85}
    performance_summary: Dict[str, List[str]]  # e.g., {"Strengths": [...], "Weaknesses": [...]}
    conversation_id: str
    timestamp: datetime

    class Meta:
        collection = "grades"  # Collection name in MongoDB

class ConversationLog(Document):
    user: User
    conversation_id: str
    transcript: list  # List of chat messages
    timestamp: datetime

    class Meta:
        collection = "conversation_logs"  # Collection name in MongoDB
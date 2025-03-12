from datetime import datetime
from beanie import Document, PydanticObjectId
from typing import Optional

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


class Grade(Document):
    user: User
    case_study: CaseStudy
    grade: int


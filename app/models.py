from beanie import Document
from typing import Optional

class User(Document):
    name: str
    email: str 
    
class CaseStudy(Document): 
    title: str
    description: str
    agent_id: Optional[str]

class Grade(Document):
    user: User
    case_study: CaseStudy
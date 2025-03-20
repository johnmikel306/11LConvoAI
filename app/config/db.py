import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv
from ..models import Session, User, CaseStudy, Grade, ConversationLog
from ..utils.logger import logger

async def setup_db():
    load_dotenv()
    
    required_vars = ["MONGO_URI", "JWT_SECRET", "ELEVENLABS_API_KEY", "AGENT_ID", "GROQ_API_KEY"]
    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Missing required environment variable: {var}")
    
    dbURI = os.getenv("MONGO_URI")
    if not dbURI:
        raise ValueError("MONGO_URI environment variable is required.")
    
    try:
        client = AsyncIOMotorClient(dbURI)
        db = client.get_database("ailp")
        
        await init_beanie(
            database=db,
            document_models=[
                User,
                CaseStudy,
                Grade,
                ConversationLog,
                Session
            ]
        )
        return db, client
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise e
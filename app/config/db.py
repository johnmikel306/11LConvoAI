import asyncio
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv
from ..utils.logger import logger
from ..models import Session, User, CaseStudy, Grade, ConversationLog 

async def setup_db():
    # Load environment variables
    load_dotenv()

    # Validate required environment variables
    required_vars = ["MONGO_URI", "JWT_SECRET", "ELEVENLABS_API_KEY", "AGENT_ID"]
    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Missing required environment variable: {var}")

    # Configure MongoDB using Beanie
    dbURI = os.getenv("MONGO_URI")
    if not dbURI:
        raise ValueError("MONGO_URI environment variable is required.")

    try:
        # Create Motor client
        client = AsyncIOMotorClient(dbURI)
        
        # Initialize Beanie with ALL document models
        await init_beanie(
            database=client.get_database("ailp"),
            document_models=[
                User,
                CaseStudy,
                Grade,
                ConversationLog,
                Session
            ]
        )
        
        # Verify connection
        await client.admin.command('ping')
        count = await User.count()
        logger.info(f"Database connected successfully. Found {count} users.")
        
        return client
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise
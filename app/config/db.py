import os
from ..models import Session, User, CaseStudy, Grade
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv
from ..utils.logger import logger

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

    # Beanie uses Motor async client under the hood 
    client = AsyncIOMotorClient(dbURI)

    # Initialize beanie with the database and document models
    await init_beanie(database=client.ailp, document_models=[User, CaseStudy, Grade, Session]) # db_name is the database name
    logger.info(f"Database connected successfully at: {dbURI}")

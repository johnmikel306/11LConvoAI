import os
from ..models import User, CaseStudy, Grade
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

async def setup_db():
  # Load environment variables
  load_dotenv()

  # Configure MongoDB using Beanie
  dbURI = os.getenv("MONGO_URI")
  dbURI = "mongodb://localhost:27017/ailp-dev" if (dbURI is None) else dbURI
  
  # Beanie uses Motor async client under the hood 
  client = AsyncIOMotorClient(dbURI)

  # Initialize beanie with the database and document models
  await init_beanie(database=client.db_name, document_models=[User, CaseStudy, Grade])
  
  print(f"Database is running at: {dbURI}")
  

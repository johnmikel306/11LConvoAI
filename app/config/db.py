import os
import time

from dotenv import load_dotenv
from mongoengine import connect

from ..utils.logger import logger


def setup_db():
    """
    Initialize database connection using Mongo Engine.
    """
    load_dotenv()

    required_vars = ["MONGO_URI", "JWT_SECRET", "ELEVENLABS_API_KEY", "GOOGLE_API_KEY"]
    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Missing required environment variable: {var}")

    db_uri = os.getenv("MONGO_URI")
    if not db_uri:
        raise ValueError("MONGO_URI environment variable is required.")

    try:

        connect(db="ailp", host=db_uri)
        logger.info("Connected to MongoDB successfully")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        try:
            time.sleep(10)
            connect(db="ailp", host=db_uri)
            logger.info("Connected to MongoDB successfully")
        except:
            try:
                time.sleep(10)
                connect(db="ailp", host=db_uri)
                logger.info("Connected to MongoDB successfully")
            except:

                raise

    return

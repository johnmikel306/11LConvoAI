import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from .config.db import setup_db
from .utils.logger import logger

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    logger.info("Starting up...")
    await setup_db()  # Initialize the database connection
    yield
    # Code to run on shutdown
    logger.info("Shutting down...")

# Initialize FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)
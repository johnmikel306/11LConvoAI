import os
from fastapi import FastAPI
from dotenv import load_dotenv
from .config.db import setup_db
from .utils.logger import logger

load_dotenv()

def init_app():
    app = FastAPI()
    
    # Initialize the database connection
    @app.on_event("startup")
    async def startup_db_client():
        await setup_db()
    
    return app

app = init_app()
import asyncio
import os
import threading
from dotenv import load_dotenv
from flask import Flask
from .routes import init_routes
from .config.db import setup_db

load_dotenv()

def init_app():
    
    app = Flask(__name__)
   
    app.secret_key = os.getenv("SECRET_KEY")
    if not app.secret_key:
        raise ValueError("SECRET_KEY environment variable is required for session management.")

    setup_db()
    init_routes(app)

    return app

app = init_app()


__all__ = ['app', 'socketio']

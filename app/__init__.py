import asyncio
import os
import threading
from dotenv import load_dotenv
from flask_cors import CORS
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
CORS(app, resources={r"/v1/*": {"origins": ["http://localhost:5173", "http://localhost:3000", "https://mind-be.miva.university", "http://localhost:5500", "http://127.0.0.1:5500"]}})


__all__ = ['app', 'socketio']

# Initialize Flask app and extensions
import os
import asyncio
from flask import Flask
from flask_socketio import SocketIO
from dotenv import load_dotenv
load_dotenv()

from .sockets import init_sockets
from .routes import init_routes
from .config.db import setup_db
from .utils.logger import logger

def init_app():
    # Initialize Flask app
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY")
    if not app.secret_key:
        raise ValueError("SECRET_KEY environment variable is required for session management.")

    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
    
    # Initialize the database connection
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(setup_db())
        logger.info("Database connection established successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to the database: {str(e)}")
    
    # Initialize routes
    init_routes(app)

    # Initialize sockets
    init_sockets(socketio)
    
    return app, socketio, loop

app, socketio, loop = init_app()

# Export app and socketio for use in other modules
__all__ = ['app', 'socketio', 'loop']

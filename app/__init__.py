import os
import eventlet
from flask import Flask
from flask_socketio import SocketIO
from dotenv import load_dotenv
load_dotenv()

from .sockets import init_sockets
from .routes import init_routes
from .config.db import setup_db
from .utils.logger import logger
from asgiref.wsgi import WsgiToAsgi

def init_app():
    # Initialize Flask app
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY")
    if not app.secret_key:
        raise ValueError("SECRET_KEY environment variable is required for session management.")
    app.asgi_app = WsgiToAsgi(app)  # Enable ASGI support

    # Initialize the database connection
    try:
        eventlet.spawn(setup_db).wait()  # Ensure the database is initialized before proceeding
        logger.info("Database connection established successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to the database: {str(e)}")
        raise e

    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
    
    # Initialize routes
    init_routes(app)

    # Initialize sockets
    init_sockets(socketio)
    
    return app, socketio

app, socketio = init_app()

# Export app and socketio for use in other modules
__all__ = ['app', 'socketio', 'loop']
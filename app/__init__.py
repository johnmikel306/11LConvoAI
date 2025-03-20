import asyncio
import os
import threading
from flask import Flask
from flask_socketio import SocketIO
from dotenv import load_dotenv
load_dotenv()

# from .sockets import init_sockets
from .routes import init_routes
from .config.db import setup_db
from .utils.logger import logger
# from asgiref.wsgi import WsgiToAsgi

def init_app():
    # Initialize Flask app
    app = Flask(__name__)
    # asgi_app = WsgiToAsgi(app)
    
    app.secret_key = os.getenv("SECRET_KEY")
    if not app.secret_key:
        raise ValueError("SECRET_KEY environment variable is required for session management.")

    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet') 
    
    # Initialize the database connection
    def run_db_setup():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(setup_db())

    # Run Beanie (MotorDB) setup in a new thread (prevents eventlet + asyncio conflict)
    db_thread = threading.Thread(target=run_db_setup)
    db_thread.start()
    
    # Initialize routes
    init_routes(app)

    # Initialize sockets
    # init_sockets(socketio)  # Commented out for now since we're not using SocketIO
    
    return app, socketio

app, socketio = init_app() # add socketio if needed

# Export app and socketio for use in other modules
__all__ = ['app', 'socketio'] # add 'socketio' if needed

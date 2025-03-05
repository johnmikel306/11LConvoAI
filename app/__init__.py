# Initialize Flask app and extensions
from flask import Flask
from flask_socketio import SocketIO
from dotenv import load_dotenv
import os
from .utils.logger import logger

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Import routes and sockets
from . import routes, sockets

# Export app and socketio for use in other modules
__all__ = ['app', 'socketio']

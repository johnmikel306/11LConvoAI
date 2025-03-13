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
  # Set the secret key
  app.secret_key = os.getenv("SECRET_KEY")
  if not app.secret_key:
   
      raise ValueError("SECRET_KEY environment variable is required for session management.")

  # Initialize SocketIO
  socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
  
  # Return the app and socketio instances
  return app, socketio

(app, socketio) = init_app()

# Init DB
asyncio.run(setup_db())

# Initialize routes
init_routes(app)

# Initialize sockets
init_sockets(socketio)

# Export app and socketio for use in other modules
__all__ = ['app', 'socketio']

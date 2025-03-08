# Initialize Flask app and extensions
import asyncio
from flask import Flask
from flask_socketio import SocketIO

from .sockets import init_sockets
from .routes import init_routes
from .config.db import setup_db

def init_app():
  # Initialize Flask app
  app = Flask(__name__)

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

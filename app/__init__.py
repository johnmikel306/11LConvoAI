import asyncio
import os
from flask import Flask
# from flask_socketio import SocketIO
from dotenv import load_dotenv
load_dotenv()

# from .sockets import init_sockets
from .routes import init_routes
from .config.db import setup_db
from .utils.logger import logger
from asgiref.wsgi import WsgiToAsgi

def init_app():
    # Initialize Flask app
    app = Flask(__name__)
    asgi_app = WsgiToAsgi(app)
    
    app.secret_key = os.getenv("SECRET_KEY")
    if not app.secret_key:
        raise ValueError("SECRET_KEY environment variable is required for session management.")

    # Initialize SocketIO
    # socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet') 
    
    # Initialize the database connection
    async def init_db():
        try:
            await asyncio.wait_for(setup_db(), timeout=30)  # ✅ Limit DB init to 30s
            logger.info("Database connection established successfully.")
        except asyncio.TimeoutError:
            logger.error("Database setup timed out!")
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")

    loop = asyncio.get_event_loop()
    loop.create_task(init_db())
    
    # Initialize routes
    init_routes(app)

    # Initialize sockets
    # init_sockets(socketio)  # Commented out for now since we're not using SocketIO
    
    return app

app = init_app() # add socketio if needed

# Export app and socketio for use in other modules
__all__ = ['app', 'asgi_app'] # add 'socketio' if needed

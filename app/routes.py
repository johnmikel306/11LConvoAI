from flask import jsonify, render_template
from .services import start_conversation, stop_conversation, get_transcript
from . import app  # Import the app variable
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_routes(app):
    @app.route('/')
    def index():
        logger.info("Rendering index page")
        return render_template('index.html')
    
    @app.route('/start', methods=['GET', 'POST'])
    def start():
        logger.info("Start conversation endpoint called")
        return start_conversation()

    @app.route('/stop', methods=['POST'])
    def stop():
        logger.info("Stop conversation endpoint called")
        return stop_conversation()

    @app.route('/transcript', methods=['GET'])
    def transcript():
        logger.info("Transcript endpoint called")
        return get_transcript()

# Initialize routes
init_routes(app)

from flask_socketio import emit
from .services import store_message
from . import socketio
from .utils.logger import logger

def init_sockets(socketio):
    @socketio.on('connect')
    def handle_connect():
        logger.info("Client connected")

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info("Client disconnected")

    @socketio.on('new_message')
    def handle_new_message(data):
        logger.info(f"New message received: {data}")
        store_message(data['sender'], data['message'])

# Initialize sockets
init_sockets(socketio)
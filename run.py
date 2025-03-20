import eventlet
eventlet.monkey_patch()

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    logger.debug("Attempting to import app and socketio...")
    from app import app, socketio
    logger.debug("Successfully imported app and socketio")
except Exception as e:
    logger.error(f"Failed to import app: {str(e)}", exc_info=True)
    raise

if __name__ == '__main__':
    try:
        logger.info("Starting server on http://0.0.0.0:8888")
        # Use eventlet WSGI server
        eventlet.wsgi.server(
            eventlet.listen(('0.0.0.0', 8888)),
            app,
            debug=True
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}", exc_info=True)
        raise

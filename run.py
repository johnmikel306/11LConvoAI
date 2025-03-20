import asyncio
from app import app, socketio

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

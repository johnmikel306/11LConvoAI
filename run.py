import eventlet
eventlet.monkey_patch()

from app import app, socketio
from app.config.db import setup_db_sync

if __name__ == '__main__':
    setup_db_sync()  # Ensure the database is initialized before starting the app
    socketio.run(app, debug=True, host='0.0.0.0', port=8888)
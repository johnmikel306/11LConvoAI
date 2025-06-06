from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

from .config.db import setup_db
from .routes import init_routes

load_dotenv()


def init_app():
    app = Flask(__name__)

    CORS(app, resources={r"/v1/*": {
        "origins": ["http://localhost:5173", "http://localhost:3000", "http://localhost:5500", "http://127.0.0.1:5500",
                    "https://mind.miva.university"]}})

    setup_db()
    init_routes(app)

    return app


app = init_app()
CORS(app, resources={r"/v1/*": {
    "origins": ["http://localhost:5173", "http://localhost:3000", "http://localhost:5500", "http://127.0.0.1:5500",
                "https://mind.miva.university"]}})

__all__ = ['app']

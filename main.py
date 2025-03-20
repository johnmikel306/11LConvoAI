from fastapi import FastAPI
from app.routes import init_routes

app = FastAPI()

# Initialize routes
init_routes(app)
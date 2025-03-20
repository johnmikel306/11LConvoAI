from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .models import Grade, Session, User
from .services import create_user_sync, get_signed_url
from .utils.cas_helper import validate_service_ticket
from .utils.jwt import token_required
from .utils.grading import grade_conversation
from .utils.logger import logger
import jwt
import os
import datetime

templates = Jinja2Templates(directory="app/templates")
security = HTTPBearer()

def init_routes(app: FastAPI):
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        logger.info("Rendering index page")
        return templates.TemplateResponse("index.html", {"request": request})
    
    @app.get("/get_signed_url")
    async def signed_url():
        try:
            logger.info("Get signed URL endpoint called")
            url = get_signed_url()
            return url
        except Exception as e:
            logger.error(f"Error in /get_signed_url: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/cas/auth-url")
    async def cas_login():
        try:
            service_url = "https://miva-mind.vercel.app/auth/cas/callback"
            cas_login_url = f"{os.getenv('CAS_LOGIN_URL')}?service={service_url}"
            logger.info(f"Redirecting to CAS login: {cas_login_url}")
            return JSONResponse(content={'url': cas_login_url})
        except Exception as e:
            logger.error(f"Error in /cas/auth-url: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/cas/validate")
    async def cas_validate(request: Request):
        try:
            form_data = await request.form()
            ticket = form_data.get("ticket")
            if not ticket:
                logger.error("Invalid request: No ticket provided.")
                raise HTTPException(status_code=400, detail="No ticket provided.")
            
            service_url = "https://miva-mind.vercel.app/auth/cas/callback"
            logger.info(f"Validating ticket: {ticket} with service URL: {service_url}")
            user_email = validate_service_ticket(ticket, service_url)
            
            if not user_email:
                raise HTTPException(status_code=401, detail="Invalid ticket")
            
            user = create_user_sync(user_email)
            
            token = jwt.encode({
                'email': user_email,
                'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
            }, os.getenv('JWT_SECRET'))
            
            return JSONResponse(content={'token': token})
        except Exception as e:
            logger.error(f"Error in /cas/validate: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/cas/logout")
    async def cas_logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
        try:
            token = credentials.credentials
            decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
            user_email = decoded.get('email')
            
            if user_email:
                active_session = await Session.find_active_by_email(user_email)
                if active_session:
                    await Session.end_session(active_session.id)
                
                logger.info(f"User {user_email} logged out.")
                return JSONResponse(content={"status": "success", "message": "User logged out."})
            else:
                logger.info("No user in session.")
                raise HTTPException(status_code=400, detail="No user in session.")
        except Exception as e:
            logger.error(f"Error in /cas/logout: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/grade/{conversation_id}")
    async def grade_conversation_endpoint(conversation_id: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
        try:
            token = credentials.credentials
            decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
            user_email = decoded.get('email')
            
            if not user_email:
                raise HTTPException(status_code=401, detail="User not authenticated")
            
            grading_result = await grade_conversation(conversation_id, user_email)
            
            return JSONResponse(content={
                "status": "success",
                "message": "Conversation graded.",
                "grading_result": grading_result
            })
        except Exception as e:
            logger.error(f"Error grading conversation: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/sessions")
    async def get_user_sessions(credentials: HTTPAuthorizationCredentials = Depends(security)):
        try:
            token = credentials.credentials
            decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
            user_email = decoded.get('email')
            
            if not user_email:
                raise HTTPException(status_code=401, detail="User not authenticated")
            
            sessions = await Session.find(Session.user_email == user_email).to_list()
            
            formatted_sessions = []
            for session in sessions:
                formatted_sessions.append({
                    "id": str(session.id),
                    "conversation_id": session.conversation_id,
                    "start_time": session.start_time.isoformat(),
                    "end_time": session.end_time.isoformat() if session.end_time else None,
                    "is_active": session.is_active,
                    "transcript_length": len(session.transcript) if session.transcript else 0
                })
                
            return JSONResponse(content={
                "status": "success",
                "sessions": formatted_sessions
            })
        except Exception as e:
            logger.error(f"Error getting user sessions: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/grades")
    async def get_user_grades(credentials: HTTPAuthorizationCredentials = Depends(security)):
        try:
            token = credentials.credentials
            decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
            user_email = decoded.get('email')
            
            if not user_email:
                raise HTTPException(status_code=401, detail="User not authenticated")
            
            user = await User.find_by_email(user_email)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            grades = await Grade.find(Grade.user.id == user.id).to_list()
            
            formatted_grades = []
            for grade in grades:
                formatted_grades.append({
                    "id": str(grade.id),
                    "conversation_id": grade.conversation_id,
                    "timestamp": grade.timestamp.isoformat(),
                    "final_score": grade.final_score,
                    "individual_scores": grade.individual_scores,
                    "performance_summary": grade.performance_summary
                })
                
            return JSONResponse(content={
                "status": "success",
                "grades": formatted_grades
            })
        except Exception as e:
            logger.error(f"Error getting user grades: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
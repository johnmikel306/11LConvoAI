from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from functools import wraps
import os
from ..services import get_user_by_email
import jwt
import asyncio

security = HTTPBearer()

def token_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        credentials: HTTPAuthorizationCredentials = Depends(security)
        token = credentials.credentials
        
        if not token:
            raise HTTPException(status_code=401, detail="Token is missing!")
        
        try:
            data = jwt.decode(token, os.getenv('JWT_SECRET'))
            email = data.get('email')
            if not email:
                raise HTTPException(status_code=401, detail="Email not found in token")
            
            user = await get_user_by_email(email)
            if not user:
                raise HTTPException(status_code=401, detail="User not found!")
            
            return await func(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired!")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Token is invalid!")
        except Exception as e:
            raise HTTPException(status_code=401, detail="Token is invalid!")
    
    return wrapper
from datetime import UTC,datetime,timedelta
import jwt
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from config import settings

password_hash=PasswordHash.recommended()

oauth2_scheme=OAuth2PasswordBearer(tokenUrl="api/users/token")

def hash_password(password:str)->str:
    return password_hash.hash(password)

def verify_password(plain_password:str,hashed_password:str)->bool:
    return password_hash.verify(plain_password,hashed_password)

def create_access_token(data:dict,expires_delta:timedelta | None =None)->str:
    to_encode=data.copy()
    if expires_delta:
        expire=datetime.now(UTC)+expires_delta
    else:
        expire=datetime.now(UTC)+timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({"exp":expire})
    encoded_jwt=jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm
    )
    return encoded_jwt

def verify_access_token(token:str)->str|None:
    try:
        payload=jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require":['exp','sub']}
        )
    except jwt.InvalidTokenError:
        return None
    else:
        return payload.get("sub")
    

# 1. Browser: 
#    POST /api/users/token (username=alice123, password=MySecurePass123!)

# 2. FastAPI → verify_password()
#    - Extracts salt from stored hash
#    - Hashes incoming password
#    - ✓ Match found

# 3. FastAPI → create_access_token({"sub": "alice123"})
#    - Creates JWT with 30-min expiration
#    - Signs with secret key
#    - Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 4. Browser stores token (localStorage/cookie)

# 5. Browser requests /api/users/profile
#    Headers: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 6. FastAPI → oauth2_scheme extracts token
#    → verify_access_token(token)
#    - Validates signature & expiration
#    - Returns "alice123"

# 7. FastAPI uses "alice123" to fetch user data from database
#    Returns profile to browser
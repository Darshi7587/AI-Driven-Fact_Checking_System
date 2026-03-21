from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone
from models.user_model import UserCreate, UserLogin, TokenResponse, UserResponse
from auth.password_handler import hash_password, verify_password
from auth.jwt_handler import create_access_token, decode_access_token
import uuid

router = APIRouter()
security = HTTPBearer()

def get_db(request: Request):
    return request.app.state.db

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None
):
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    db = request.app.state.db
    user = await db.users.find_one({"email": payload.get("sub")})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate, request: Request):
    db = get_db(request)
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    hashed = hash_password(user_data.password)
    now = datetime.now(timezone.utc).isoformat()
    
    user_doc = {
        "_id": user_id,
        "name": user_data.name,
        "email": user_data.email,
        "password": hashed,
        "avatar": f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_data.name}",
        "created_at": now,
        "total_checks": 0
    }
    await db.users.insert_one(user_doc)
    
    token = create_access_token({"sub": user_data.email, "user_id": user_id})
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            name=user_data.name,
            email=user_data.email,
            avatar=user_doc["avatar"],
            created_at=now
        )
    )

@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, request: Request):
    db = get_db(request)
    user = await db.users.find_one({"email": user_data.email})
    if not user or not verify_password(user_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token({"sub": user["email"], "user_id": user["_id"]})
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["_id"],
            name=user["name"],
            email=user["email"],
            avatar=user.get("avatar"),
            created_at=user["created_at"]
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_me(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    db = get_db(request)
    user = await db.users.find_one({"email": payload.get("sub")})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=user["_id"],
        name=user["name"],
        email=user["email"],
        avatar=user.get("avatar"),
        created_at=user["created_at"]
    )

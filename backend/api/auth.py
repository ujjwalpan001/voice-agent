"""
Authentication API – JWT-based admin login.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from backend.config import settings
from backend.database.mongodb import get_admins_col
from backend.models.admin import AdminResponse, TokenResponse, LoginRequest, AdminCreate
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_admin(token: str = Depends(oauth2_scheme)) -> AdminResponse:
    payload = decode_token(token)
    username: str = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    col = get_admins_col()
    admin = await col.find_one({"username": username})
    if not admin:
        raise HTTPException(status_code=401, detail="Admin not found")
    return AdminResponse(
        id=str(admin["_id"]),
        username=admin["username"],
        email=admin["email"],
        full_name=admin.get("full_name"),
        is_active=admin.get("is_active", True),
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/has-admin")
async def has_admin():
    col = get_admins_col()
    count = await col.count_documents({})
    return {"has_admin": count > 0}

@router.post("/setup", response_model=TokenResponse)
async def setup_admin(admin_data: AdminCreate):
    col = get_admins_col()
    if await col.count_documents({}) > 0:
        raise HTTPException(status_code=400, detail="Admin already exists")
    
    hashed = hash_password(admin_data.password)
    new_admin = {
        "username": admin_data.username,
        "email": admin_data.email,
        "full_name": admin_data.full_name,
        "hashed_password": hashed,
        "is_active": True,
    }
    result = await col.insert_one(new_admin)
    new_admin["_id"] = result.inserted_id
    token = create_access_token({"sub": admin_data.username})
    return TokenResponse(
        access_token=token,
        admin=AdminResponse(
            id=str(new_admin["_id"]),
            username=new_admin["username"],
            email=new_admin["email"],
            full_name=new_admin.get("full_name"),
            is_active=new_admin["is_active"],
        ),
    )

@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    col = get_admins_col()
    admin = await col.find_one({"username": form_data.username})
    if not admin or not verify_password(form_data.password, admin["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": admin["username"]})
    return TokenResponse(
        access_token=token,
        admin=AdminResponse(
            id=str(admin["_id"]),
            username=admin["username"],
            email=admin["email"],
            full_name=admin.get("full_name"),
            is_active=admin.get("is_active", True),
        ),
    )


@router.get("/me", response_model=AdminResponse)
async def get_me(current_admin: AdminResponse = Depends(get_current_admin)):
    return current_admin

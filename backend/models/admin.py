"""
Pydantic models for Admin and authentication.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class AdminCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class AdminInDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    username: str
    email: str
    full_name: Optional[str] = None
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class AdminResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminResponse

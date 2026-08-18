"""
Pydantic models for Menu items and categories.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class MenuCategory(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    display_order: int = 0
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MenuItemCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    price: float
    available: bool = True
    ingredients: List[str] = []
    dietary_tags: List[str] = []   # e.g. ["veg", "gluten-free"]
    image_url: Optional[str] = None
    preparation_time_minutes: Optional[int] = None
    calories: Optional[int] = None


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    available: Optional[bool] = None
    ingredients: Optional[List[str]] = None
    dietary_tags: Optional[List[str]] = None
    image_url: Optional[str] = None
    preparation_time_minutes: Optional[int] = None
    calories: Optional[int] = None


class MenuItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    category: str
    price: float
    available: bool = True
    ingredients: List[str] = []
    dietary_tags: List[str] = []
    image_url: Optional[str] = None
    preparation_time_minutes: Optional[int] = None
    calories: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True

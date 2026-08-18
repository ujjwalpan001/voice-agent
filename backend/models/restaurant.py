"""
Restaurant settings model.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class OpeningHours(BaseModel):
    monday: str = "9:00 AM - 10:00 PM"
    tuesday: str = "9:00 AM - 10:00 PM"
    wednesday: str = "9:00 AM - 10:00 PM"
    thursday: str = "9:00 AM - 10:00 PM"
    friday: str = "9:00 AM - 11:00 PM"
    saturday: str = "9:00 AM - 11:00 PM"
    sunday: str = "10:00 AM - 10:00 PM"


class RestaurantSettings(BaseModel):
    name: str = "My Restaurant"
    tagline: Optional[str] = None
    cuisine_types: List[str] = []
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    opening_hours: OpeningHours = Field(default_factory=OpeningHours)
    is_open: bool = True
    accepts_delivery: bool = True
    accepts_pickup: bool = True
    min_order_amount: float = 0.0
    estimated_delivery_time: str = "30-45 minutes"
    policies: Optional[str] = None  # free-text restaurant policy block
    faqs: List[Dict[str, str]] = []  # [{"question": "...", "answer": "..."}]
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RestaurantSettingsUpdate(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    cuisine_types: Optional[List[str]] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[OpeningHours] = None
    is_open: Optional[bool] = None
    accepts_delivery: Optional[bool] = None
    accepts_pickup: Optional[bool] = None
    min_order_amount: Optional[float] = None
    estimated_delivery_time: Optional[str] = None
    policies: Optional[str] = None
    faqs: Optional[List[Dict[str, str]]] = None

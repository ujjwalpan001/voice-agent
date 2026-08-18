"""
Pydantic models for Orders.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderItem(BaseModel):
    item_id: str
    name: str
    category: str
    quantity: int
    unit_price: float
    total_price: float
    special_instructions: Optional[str] = None


class DeliveryInfo(BaseModel):
    type: str = "delivery"  # "delivery" | "pickup"
    address: Optional[str] = None
    landmark: Optional[str] = None
    instructions: Optional[str] = None


class OrderCreate(BaseModel):
    customer_name: str
    customer_phone: str
    call_id: str
    conversation_id: str
    items: List[OrderItem]
    delivery_info: Optional[DeliveryInfo] = None
    special_notes: Optional[str] = None


class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_name: str
    customer_phone: str
    call_id: str
    conversation_id: str
    items: List[OrderItem]
    delivery_info: Optional[DeliveryInfo] = None
    special_notes: Optional[str] = None

    # Billing
    subtotal: float = 0.0
    tax_amount: float = 0.0
    tax_percentage: float = 0.0
    delivery_charge: float = 0.0
    discount_amount: float = 0.0
    grand_total: float = 0.0

    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class CartItem(BaseModel):
    item_id: str
    name: str
    category: str
    quantity: int
    unit_price: float
    total_price: float
    special_instructions: Optional[str] = None


class Cart(BaseModel):
    call_id: str
    customer_phone: str
    items: List[CartItem] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

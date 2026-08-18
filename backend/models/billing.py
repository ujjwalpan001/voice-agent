"""
Billing configuration and calculation models.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BillingConfig(BaseModel):
    tax_percentage: float = 5.0
    delivery_charge: float = 30.0
    free_delivery_above: float = 500.0   # free delivery if order > this amount
    discount_percentage: float = 0.0
    discount_code: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BillingConfigUpdate(BaseModel):
    tax_percentage: Optional[float] = None
    delivery_charge: Optional[float] = None
    free_delivery_above: Optional[float] = None
    discount_percentage: Optional[float] = None
    discount_code: Optional[str] = None


class BillCalculation(BaseModel):
    items_total: float
    subtotal: float
    tax_percentage: float
    tax_amount: float
    delivery_charge: float
    discount_percentage: float
    discount_amount: float
    grand_total: float
    is_free_delivery: bool = False

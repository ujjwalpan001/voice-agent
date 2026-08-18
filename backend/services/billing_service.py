"""
Billing service – all monetary calculations happen here (server-side).
"""
import logging
from typing import List
from backend.database.mongodb import get_billing_config_col
from backend.models.billing import BillingConfig, BillCalculation
from backend.models.order import CartItem

logger = logging.getLogger(__name__)


async def get_billing_config() -> BillingConfig:
    """Load billing config from DB; return defaults if none stored."""
    col = get_billing_config_col()
    doc = await col.find_one({})
    if doc:
        doc.pop("_id", None)
        return BillingConfig(**doc)
    return BillingConfig()


async def save_billing_config(config: BillingConfig) -> BillingConfig:
    col = get_billing_config_col()
    data = config.model_dump()
    await col.replace_one({}, data, upsert=True)
    return config


async def calculate_bill(
    items: List[CartItem],
    delivery_type: str = "delivery",
) -> BillCalculation:
    """
    Calculate a full bill from cart items.
    All numbers are computed server-side using the DB config.
    """
    config = await get_billing_config()

    subtotal = sum(item.total_price for item in items)

    # Free delivery logic
    is_free_delivery = (
        delivery_type == "delivery"
        and subtotal >= config.free_delivery_above
    )
    delivery_charge = 0.0 if is_free_delivery else (
        config.delivery_charge if delivery_type == "delivery" else 0.0
    )

    # Discount
    discount_amount = round(subtotal * config.discount_percentage / 100, 2)
    taxable_amount = subtotal - discount_amount

    # Tax / GST
    tax_amount = round(taxable_amount * config.tax_percentage / 100, 2)

    grand_total = round(taxable_amount + tax_amount + delivery_charge, 2)

    return BillCalculation(
        items_total=round(subtotal, 2),
        subtotal=round(subtotal, 2),
        tax_percentage=config.tax_percentage,
        tax_amount=tax_amount,
        delivery_charge=delivery_charge,
        discount_percentage=config.discount_percentage,
        discount_amount=discount_amount,
        grand_total=grand_total,
        is_free_delivery=is_free_delivery,
    )

"""
Order creation, status management, and retrieval tools.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.database.mongodb import get_orders_col, get_carts_col
from backend.models.order import Order, OrderStatus, OrderItem, DeliveryInfo
from backend.services.billing_service import calculate_bill

logger = logging.getLogger(__name__)


async def create_order_from_cart(
    call_id: str,
    conversation_id: str,
    customer_name: str,
    customer_phone: str,
    delivery_info: Optional[Dict[str, Any]] = None,
    special_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a confirmed order from the active cart.
    Billing is computed server-side.
    """
    cart_col = get_carts_col()
    cart = await cart_col.find_one({"call_id": call_id})
    if not cart or not cart.get("items"):
        return {"success": False, "error": "Cart is empty or not found."}

    delivery_type = delivery_info.get("type", "delivery") if delivery_info else "delivery"
    cart_items_raw = cart["items"]

    # Convert to CartItem models for billing
    from backend.models.order import CartItem
    cart_items = [CartItem(**i) for i in cart_items_raw]
    bill = await calculate_bill(cart_items, delivery_type=delivery_type)

    order_items = [
        OrderItem(
            item_id=i.item_id,
            name=i.name,
            category=i.category,
            quantity=i.quantity,
            unit_price=i.unit_price,
            total_price=i.total_price,
            special_instructions=i.special_instructions,
        )
        for i in cart_items
    ]

    d_info = DeliveryInfo(**delivery_info) if delivery_info else None

    order = Order(
        customer_name=customer_name,
        customer_phone=customer_phone,
        call_id=call_id,
        conversation_id=conversation_id,
        items=order_items,
        delivery_info=d_info,
        special_notes=special_notes,
        subtotal=bill.subtotal,
        tax_amount=bill.tax_amount,
        tax_percentage=bill.tax_percentage,
        delivery_charge=bill.delivery_charge,
        discount_amount=bill.discount_amount,
        grand_total=bill.grand_total,
        status=OrderStatus.PENDING,
    )
    orders_col = get_orders_col()
    await orders_col.insert_one(order.model_dump())

    # Clear the cart after order creation
    await cart_col.update_one(
        {"call_id": call_id},
        {"$set": {"items": [], "updated_at": datetime.utcnow()}},
    )
    logger.info(f"Order {order.id} created for {customer_phone}.")
    return {
        "success": True,
        "order_id": order.id,
        "grand_total": bill.grand_total,
        "status": order.status,
    }


async def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single order by its ID."""
    col = get_orders_col()
    doc = await col.find_one({"id": order_id}, {"_id": 0})
    return doc


async def get_orders_by_phone(customer_phone: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Return recent orders for a customer phone number."""
    col = get_orders_col()
    cursor = col.find(
        {"customer_phone": customer_phone},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def cancel_order(order_id: str) -> Dict[str, Any]:
    """Cancel a pending or confirmed order."""
    col = get_orders_col()
    result = await col.update_one(
        {"id": order_id, "status": {"$in": ["pending", "confirmed"]}},
        {"$set": {"status": OrderStatus.CANCELLED, "updated_at": datetime.utcnow()}},
    )
    if result.modified_count:
        return {"success": True, "order_id": order_id}
    return {"success": False, "error": "Order not found or cannot be cancelled."}


def format_order_for_voice(order: Dict[str, Any]) -> str:
    """Format order details as a natural language summary."""
    items = order.get("items", [])
    item_str = ", ".join(f"{i['quantity']}x {i['name']}" for i in items)
    return (
        f"Order {order['id'][:8]}: {item_str}. "
        f"Total ₹{order['grand_total']:.0f}. Status: {order['status']}."
    )

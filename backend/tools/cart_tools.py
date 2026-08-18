"""
Cart management tools.
Cart state is authoritative from MongoDB (keyed by call_id).
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.database.mongodb import get_carts_col, get_menu_items_col
from backend.models.order import Cart, CartItem

logger = logging.getLogger(__name__)


async def _get_or_create_cart(call_id: str, customer_phone: str) -> Dict[str, Any]:
    col = get_carts_col()
    doc = await col.find_one({"call_id": call_id})
    if not doc:
        cart = Cart(call_id=call_id, customer_phone=customer_phone)
        await col.insert_one(cart.model_dump())
        return cart.model_dump()
    return doc


async def get_cart(call_id: str) -> Optional[Dict[str, Any]]:
    """Return the current cart for a call."""
    col = get_carts_col()
    doc = await col.find_one({"call_id": call_id}, {"_id": 0})
    return doc


async def add_to_cart(
    call_id: str,
    customer_phone: str,
    item_id: str,
    quantity: int = 1,
    special_instructions: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add or increment an item in the cart.
    Price is always fetched from MongoDB (source of truth).
    """
    menu_col = get_menu_items_col()
    item = await menu_col.find_one({"id": item_id, "available": True}, {"_id": 0})
    if not item:
        return {"success": False, "error": f"Item {item_id!r} not found or unavailable."}

    cart_col = get_carts_col()
    cart = await _get_or_create_cart(call_id, customer_phone)

    items: List[Dict[str, Any]] = cart.get("items", [])
    unit_price = item["price"]

    # Check if item already exists in cart
    for existing in items:
        if existing["item_id"] == item_id:
            existing["quantity"] += quantity
            existing["total_price"] = round(existing["quantity"] * unit_price, 2)
            if special_instructions:
                existing["special_instructions"] = special_instructions
            break
    else:
        items.append({
            "item_id": item_id,
            "name": item["name"],
            "category": item.get("category", ""),
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": round(quantity * unit_price, 2),
            "special_instructions": special_instructions,
        })

    await cart_col.update_one(
        {"call_id": call_id},
        {"$set": {"items": items, "updated_at": datetime.utcnow()}},
    )
    return {"success": True, "item_name": item["name"], "quantity": quantity, "cart_total_items": len(items)}


async def remove_from_cart(
    call_id: str,
    item_id: str,
) -> Dict[str, Any]:
    """Remove an item entirely from the cart."""
    cart_col = get_carts_col()
    cart = await get_cart(call_id)
    if not cart:
        return {"success": False, "error": "Cart not found."}

    original_len = len(cart.get("items", []))
    items = [i for i in cart.get("items", []) if i["item_id"] != item_id]

    if len(items) == original_len:
        return {"success": False, "error": "Item not in cart."}

    await cart_col.update_one(
        {"call_id": call_id},
        {"$set": {"items": items, "updated_at": datetime.utcnow()}},
    )
    return {"success": True, "removed_item_id": item_id}


async def update_cart_quantity(
    call_id: str,
    item_id: str,
    quantity: int,
) -> Dict[str, Any]:
    """Update the quantity of an item in the cart. Set to 0 to remove."""
    if quantity <= 0:
        return await remove_from_cart(call_id, item_id)

    cart_col = get_carts_col()
    cart = await get_cart(call_id)
    if not cart:
        return {"success": False, "error": "Cart not found."}

    items = cart.get("items", [])
    updated = False
    for item in items:
        if item["item_id"] == item_id:
            item["quantity"] = quantity
            item["total_price"] = round(quantity * item["unit_price"], 2)
            updated = True
            break

    if not updated:
        return {"success": False, "error": "Item not in cart."}

    await cart_col.update_one(
        {"call_id": call_id},
        {"$set": {"items": items, "updated_at": datetime.utcnow()}},
    )
    return {"success": True, "item_id": item_id, "new_quantity": quantity}


async def clear_cart(call_id: str) -> Dict[str, Any]:
    """Empty the cart completely."""
    cart_col = get_carts_col()
    await cart_col.update_one(
        {"call_id": call_id},
        {"$set": {"items": [], "updated_at": datetime.utcnow()}},
    )
    return {"success": True}


def format_cart_for_voice(cart: Dict[str, Any]) -> str:
    """Convert cart to a natural speech-friendly summary."""
    items = cart.get("items", [])
    if not items:
        return "Your cart is empty."
    parts = []
    total = 0.0
    for item in items:
        parts.append(f"{item['quantity']}x {item['name']} – ₹{item['total_price']:.0f}")
        total += item["total_price"]
    return f"Cart: {', '.join(parts)}. Subtotal: ₹{total:.0f}."

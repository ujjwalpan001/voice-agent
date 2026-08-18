"""
Billing tools for the agent.
All calculations are server-side; the LLM only displays results.
"""
from typing import Any, Dict, List, Optional
from backend.services.billing_service import calculate_bill, get_billing_config
from backend.models.order import CartItem


async def get_bill_preview(
    call_id: str,
    delivery_type: str = "delivery",
) -> Dict[str, Any]:
    """
    Calculate a bill preview for the current cart.
    Returns a structured dict the agent can read aloud.
    """
    from backend.tools.cart_tools import get_cart
    cart = await get_cart(call_id)
    if not cart or not cart.get("items"):
        return {"success": False, "error": "Cart is empty."}

    cart_items = [CartItem(**i) for i in cart["items"]]
    bill = await calculate_bill(cart_items, delivery_type)
    return {
        "success": True,
        "subtotal": bill.subtotal,
        "tax_percentage": bill.tax_percentage,
        "tax_amount": bill.tax_amount,
        "delivery_charge": bill.delivery_charge,
        "discount_amount": bill.discount_amount,
        "grand_total": bill.grand_total,
        "is_free_delivery": bill.is_free_delivery,
    }


def format_bill_for_voice(bill: Dict[str, Any]) -> str:
    """Format a bill summary as a readable voice string."""
    parts = [f"Subtotal ₹{bill['subtotal']:.0f}"]
    if bill.get("discount_amount", 0) > 0:
        parts.append(f"discount ₹{bill['discount_amount']:.0f}")
    parts.append(f"GST ₹{bill['tax_amount']:.0f}")
    if bill.get("delivery_charge", 0) > 0:
        parts.append(f"delivery ₹{bill['delivery_charge']:.0f}")
    parts.append(f"Grand total ₹{bill['grand_total']:.0f}")
    return ", ".join(parts) + "."

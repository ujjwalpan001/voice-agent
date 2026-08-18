"""
Menu tools for the LangGraph agent.
All menu data is authoritative from MongoDB.
"""
import logging
from typing import Any, Dict, List, Optional
from backend.database.mongodb import get_menu_items_col

logger = logging.getLogger(__name__)


async def search_menu(
    query: str,
    category: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Search menu items by name or description (case-insensitive regex).
    Optionally filter by category. Only returns available items.
    """
    col = get_menu_items_col()
    filter_doc: Dict[str, Any] = {
        "available": True,
        "$or": [
            {"name": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}},
        ],
    }
    if category:
        filter_doc["category"] = {"$regex": category, "$options": "i"}

    cursor = col.find(filter_doc, {"_id": 0}).limit(limit)
    return await cursor.to_list(length=limit)


async def get_menu_item_by_id(item_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single menu item by its ID."""
    col = get_menu_items_col()
    return await col.find_one({"id": item_id}, {"_id": 0})


async def get_menu_item_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Find the best matching available menu item by name."""
    col = get_menu_items_col()
    return await col.find_one(
        {"name": {"$regex": name, "$options": "i"}, "available": True},
        {"_id": 0},
    )


async def get_all_categories() -> List[str]:
    """Return all distinct menu categories that have available items."""
    col = get_menu_items_col()
    cats = await col.distinct("category", {"available": True})
    return sorted(cats)


async def get_items_by_category(category: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch all available items in a given category."""
    col = get_menu_items_col()
    cursor = col.find(
        {"category": {"$regex": category, "$options": "i"}, "available": True},
        {"_id": 0},
    ).limit(limit)
    return await cursor.to_list(length=limit)


async def check_item_availability(item_id: str) -> Dict[str, Any]:
    """Check if a specific item is currently available."""
    item = await get_menu_item_by_id(item_id)
    if not item:
        return {"available": False, "reason": "Item not found"}
    return {"available": item.get("available", False), "item": item}


def format_menu_items_for_voice(items: List[Dict[str, Any]]) -> str:
    """Format a list of menu items into a natural speech-friendly string."""
    if not items:
        return "No items found."
    parts = []
    for item in items:
        price = item.get("price", 0)
        parts.append(
            f"{item['name']} – ₹{price:.0f}"
            + (f" ({item.get('description', '')})" if item.get("description") else "")
        )
    return "; ".join(parts)

"""
Customer memory tools.
Loads and stores long-term customer profile from MongoDB.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.database.mongodb import get_customers_col, get_customer_memory_col

logger = logging.getLogger(__name__)


async def get_customer_profile(phone: str) -> Optional[Dict[str, Any]]:
    """Load a customer profile by phone number."""
    col = get_customers_col()
    doc = await col.find_one({"phone": phone}, {"_id": 0})
    return doc


async def upsert_customer(
    phone: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update a customer record."""
    col = get_customers_col()
    update: Dict[str, Any] = {"$set": {"updated_at": datetime.utcnow()}}
    if name:
        update["$set"]["name"] = name
    update["$setOnInsert"] = {
        "phone": phone,
        "created_at": datetime.utcnow(),
        "order_count": 0,
    }
    await col.update_one({"phone": phone}, update, upsert=True)
    return await get_customer_profile(phone) or {}


async def get_customer_memory(phone: str) -> Optional[Dict[str, Any]]:
    """Return long-term memory for a customer (preferences, history summary)."""
    col = get_customer_memory_col()
    doc = await col.find_one({"phone": phone}, {"_id": 0})
    return doc


async def update_customer_memory(
    phone: str,
    conversation_summary: Optional[str] = None,
    frequently_ordered: Optional[List[str]] = None,
    preferences: Optional[str] = None,
) -> None:
    """Update the customer's long-term memory store."""
    col = get_customer_memory_col()
    update: Dict[str, Any] = {"$set": {"updated_at": datetime.utcnow()}}
    if conversation_summary:
        update["$push"] = {"conversation_summaries": {
            "summary": conversation_summary,
            "timestamp": datetime.utcnow(),
        }}
        update["$set"]["last_conversation_summary"] = conversation_summary
    if frequently_ordered:
        update["$addToSet"] = {"frequently_ordered": {"$each": frequently_ordered}}
    if preferences:
        update["$set"]["preferences"] = preferences
    update.setdefault("$setOnInsert", {"phone": phone, "created_at": datetime.utcnow()})
    await col.update_one({"phone": phone}, update, upsert=True)


def format_customer_memory_for_prompt(memory: Optional[Dict[str, Any]]) -> str:
    """Produce a memory context block for the system prompt."""
    if not memory:
        return "No previous customer history."
    parts = []
    if memory.get("name"):
        parts.append(f"Customer name: {memory['name']}")
    if memory.get("last_conversation_summary"):
        parts.append(f"Last visit summary: {memory['last_conversation_summary']}")
    if memory.get("frequently_ordered"):
        items = ", ".join(memory["frequently_ordered"][:5])
        parts.append(f"Frequently orders: {items}")
    if memory.get("preferences"):
        parts.append(f"Preferences: {memory['preferences']}")
    return "\n".join(parts) if parts else "No significant history."

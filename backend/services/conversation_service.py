"""
Conversation persistence service.
Saves and retrieves full conversation messages for each call.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.database.mongodb import get_conversations_col, get_call_logs_col

logger = logging.getLogger(__name__)


async def save_message(
    call_id: str,
    customer_phone: str,
    role: str,
    content: str,
) -> None:
    """Append a single message to the conversation log."""
    col = get_conversations_col()
    await col.update_one(
        {"call_id": call_id},
        {
            "$setOnInsert": {
                "call_id": call_id,
                "customer_phone": customer_phone,
                "created_at": datetime.utcnow(),
            },
            "$push": {
                "messages": {
                    "role": role,
                    "content": content,
                    "timestamp": datetime.utcnow(),
                }
            },
            "$set": {"updated_at": datetime.utcnow()},
        },
        upsert=True,
    )


async def get_conversation(call_id: str) -> Optional[Dict[str, Any]]:
    """Return full conversation document for a call."""
    col = get_conversations_col()
    doc = await col.find_one({"call_id": call_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def get_conversation_messages(call_id: str) -> List[Dict[str, Any]]:
    """Return ordered messages for a call."""
    doc = await get_conversation(call_id)
    return doc.get("messages", []) if doc else []


async def start_call_log(
    call_id: str,
    customer_phone: str,
    twilio_sid: Optional[str] = None,
) -> None:
    """Create or initialise a call log entry."""
    col = get_call_logs_col()
    await col.update_one(
        {"call_id": call_id},
        {
            "$setOnInsert": {
                "call_id": call_id,
                "customer_phone": customer_phone,
                "twilio_sid": twilio_sid,
                "created_at": datetime.utcnow(),
                "status": "active",
            },
            "$set": {"updated_at": datetime.utcnow()},
        },
        upsert=True,
    )


async def end_call_log(
    call_id: str,
    duration_seconds: Optional[int] = None,
    order_id: Optional[str] = None,
) -> None:
    """Mark a call as ended and record metadata."""
    col = get_call_logs_col()
    update: Dict[str, Any] = {
        "$set": {
            "status": "ended",
            "ended_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    }
    if duration_seconds is not None:
        update["$set"]["duration_seconds"] = duration_seconds
    if order_id:
        update["$set"]["order_id"] = order_id
    await col.update_one({"call_id": call_id}, update)

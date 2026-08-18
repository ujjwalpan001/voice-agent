"""
Long-term and short-term memory management for the agent.
"""
import logging
from typing import Any, Dict, Optional
from backend.tools.customer_tools import (
    get_customer_memory,
    get_customer_profile,
    format_customer_memory_for_prompt,
    upsert_customer,
    update_customer_memory,
)

logger = logging.getLogger(__name__)


async def load_customer_context(phone: str) -> Dict[str, Any]:
    """
    Load customer profile and long-term memory for a phone number.
    Returns a dict with 'customer_name' and 'customer_memory' string.
    """
    profile = await get_customer_profile(phone)
    memory = await get_customer_memory(phone)

    customer_name: Optional[str] = None
    if profile:
        customer_name = profile.get("name")

    memory_str = format_customer_memory_for_prompt(memory or (profile or {}))
    return {
        "customer_name": customer_name,
        "customer_memory": memory_str,
    }


async def persist_conversation_summary(
    phone: str,
    summary: str,
    ordered_item_names: Optional[list] = None,
) -> None:
    """
    After a call ends, persist a summary to long-term memory.
    """
    await update_customer_memory(
        phone=phone,
        conversation_summary=summary,
        frequently_ordered=ordered_item_names or [],
    )
    logger.info(f"Long-term memory updated for {phone}.")


async def ensure_customer_record(phone: str, name: Optional[str] = None) -> None:
    """Create or update a customer record whenever a call is received."""
    await upsert_customer(phone=phone, name=name)

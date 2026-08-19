"""
Async MongoDB connection manager using Motor.
All database collections are exposed as module-level accessors.
"""
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect_db() -> None:
    """
    Establish MongoDB connection.
    Works with both local MongoDB and MongoDB Atlas (mongodb+srv://).
    """
    global _client, _db
    _client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=10_000,   # Generous for Atlas cold-start
        connectTimeoutMS=10_000,
        socketTimeoutMS=20_000,
    )
    _db = _client[settings.MONGODB_DB_NAME]
    # Ping to verify the connection is alive before returning
    await _db.command("ping")
    await _ensure_indexes()
    logger.info(f"MongoDB connected: {settings.MONGODB_DB_NAME}")


async def close_db() -> None:
    """Close MongoDB connection."""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db


# ─── Collection accessors ─────────────────────────────────────────────────────

def get_admins_col():
    return get_db()["admins"]

def get_restaurants_col():
    return get_db()["restaurants"]

def get_menu_items_col():
    return get_db()["menu_items"]

def get_menu_categories_col():
    return get_db()["menu_categories"]

def get_orders_col():
    return get_db()["orders"]

def get_carts_col():
    return get_db()["carts"]

def get_customers_col():
    return get_db()["customers"]

def get_conversations_col():
    return get_db()["conversations"]

def get_call_logs_col():
    return get_db()["call_logs"]

def get_billing_config_col():
    return get_db()["billing_config"]

def get_restaurant_settings_col():
    return get_db()["restaurant_settings"]

def get_customer_memory_col():
    return get_db()["customer_memory"]


# ─── Index creation ───────────────────────────────────────────────────────────

async def _ensure_indexes() -> None:
    db = get_db()

    await db["menu_items"].create_index([("category", ASCENDING)])
    await db["menu_items"].create_index([("available", ASCENDING)])
    await db["menu_items"].create_index([("name", ASCENDING)])

    await db["orders"].create_index([("customer_phone", ASCENDING)])
    await db["orders"].create_index([("status", ASCENDING)])
    await db["orders"].create_index([("created_at", DESCENDING)])
    await db["orders"].create_index([("call_id", ASCENDING)])

    await db["carts"].create_index([("call_id", ASCENDING)], unique=True)

    await db["customers"].create_index([("phone", ASCENDING)], unique=True)

    await db["conversations"].create_index([("call_id", ASCENDING)])
    await db["conversations"].create_index([("customer_phone", ASCENDING)])

    await db["call_logs"].create_index([("call_id", ASCENDING)], unique=True)
    await db["call_logs"].create_index([("customer_phone", ASCENDING)])
    await db["call_logs"].create_index([("created_at", DESCENDING)])

    await db["customer_memory"].create_index([("phone", ASCENDING)], unique=True)

    logger.info("MongoDB indexes ensured.")

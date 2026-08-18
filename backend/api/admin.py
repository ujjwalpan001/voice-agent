"""
Restaurant admin settings API.
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from backend.api.auth import get_current_admin
from backend.database.mongodb import get_restaurant_settings_col
from backend.models.admin import AdminResponse
from backend.models.restaurant import RestaurantSettings, RestaurantSettingsUpdate

router = APIRouter(prefix="/admin", tags=["Admin"])


async def _get_settings() -> dict:
    col = get_restaurant_settings_col()
    doc = await col.find_one({})
    if doc:
        doc.pop("_id", None)
        return doc
    return RestaurantSettings().model_dump()


@router.get("/settings")
async def get_restaurant_settings(_: AdminResponse = Depends(get_current_admin)):
    return await _get_settings()


@router.put("/settings")
async def update_restaurant_settings(
    updates: RestaurantSettingsUpdate,
    _: AdminResponse = Depends(get_current_admin),
):
    current = await _get_settings()
    for k, v in updates.model_dump().items():
        if v is not None:
            current[k] = v if not hasattr(v, "model_dump") else v.model_dump()
    current["updated_at"] = datetime.utcnow()
    col = get_restaurant_settings_col()
    await col.replace_one({}, current, upsert=True)
    return current

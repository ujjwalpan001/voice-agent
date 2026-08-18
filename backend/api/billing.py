"""
Billing configuration API.
"""
from fastapi import APIRouter, Depends
from backend.api.auth import get_current_admin
from backend.models.admin import AdminResponse
from backend.models.billing import BillingConfigUpdate
from backend.services.billing_service import get_billing_config, save_billing_config

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.get("/config")
async def get_config(_: AdminResponse = Depends(get_current_admin)):
    config = await get_billing_config()
    return config.model_dump()


@router.put("/config")
async def update_config(
    updates: BillingConfigUpdate,
    _: AdminResponse = Depends(get_current_admin),
):
    from datetime import datetime
    config = await get_billing_config()
    data = config.model_dump()
    for k, v in updates.model_dump().items():
        if v is not None:
            data[k] = v
    data["updated_at"] = datetime.utcnow()
    from backend.models.billing import BillingConfig
    new_config = BillingConfig(**data)
    await save_billing_config(new_config)
    return new_config.model_dump()

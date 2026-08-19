"""
Call and conversation history API.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from backend.api.auth import get_current_admin
from backend.database.mongodb import get_call_logs_col, get_conversations_col
from backend.models.admin import AdminResponse
from backend.config import settings
from twilio.rest import Client

router = APIRouter(prefix="/calls", tags=["Calls"])


@router.get("")
async def list_calls(
    customer_phone: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: AdminResponse = Depends(get_current_admin),
):
    col = get_call_logs_col()
    filter_doc = {}
    if customer_phone:
        filter_doc["customer_phone"] = customer_phone
    if status:
        filter_doc["status"] = status
    skip = (page - 1) * limit
    total = await col.count_documents(filter_doc)
    cursor = col.find(filter_doc, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    calls = await cursor.to_list(length=limit)
    return {"calls": calls, "total": total, "page": page, "limit": limit}


@router.get("/{call_id}")
async def get_call(
    call_id: str,
    _: AdminResponse = Depends(get_current_admin),
):
    col = get_call_logs_col()
    call = await col.find_one({"call_id": call_id}, {"_id": 0})
    if not call:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Call not found")
    return call


@router.get("/{call_id}/conversation")
async def get_call_conversation(
    call_id: str,
    _: AdminResponse = Depends(get_current_admin),
):
    col = get_conversations_col()
    conv = await col.find_one({"call_id": call_id}, {"_id": 0})
    if not conv:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/trigger-outbound")
async def trigger_outbound_call(
    _: AdminResponse = Depends(get_current_admin),
):
    if not settings.TEST_PHONE_NUMBER:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="TEST_PHONE_NUMBER is not set in environment variables.")

    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        # Using the same incoming webhook URL to trigger Pipecat pipeline when answered
        webhook_url = f"{settings.TWILIO_WEBHOOK_BASE_URL.rstrip('/')}/api/twilio/incoming"
        
        call = client.calls.create(
            to=settings.TEST_PHONE_NUMBER,
            from_=settings.TWILIO_PHONE_NUMBER,
            url=webhook_url
        )
        return {"status": "success", "message": f"Calling {settings.TEST_PHONE_NUMBER}...", "call_sid": call.sid}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {str(e)}")

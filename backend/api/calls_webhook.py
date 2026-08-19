"""
Twilio webhook endpoints – voice call entry point.

With pipecat integration the /incoming endpoint now returns
<Connect><Stream> TwiML, which makes Twilio open a WebSocket
to our /api/ws/voice/{call_id} endpoint and stream raw audio
bidirectionally in real time.

The old <Gather> polling approach is kept as a fallback
at /twilio/speech/{call_id} but is no longer the primary path.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import PlainTextResponse

from backend.config import settings
from backend.agent.memory import ensure_customer_record
from backend.services.conversation_service import end_call_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twilio", tags=["Telephony"])


def _stream_twiml(call_id: str, customer_phone: str) -> str:
    """
    Generate TwiML that opens a Media Stream WebSocket to our server.
    Twilio will stream raw mulaw 8kHz audio bidirectionally.
    """
    base = settings.TWILIO_WEBHOOK_BASE_URL.rstrip("/")
    # Convert https:// → wss:// for the WebSocket URL
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_base}/api/ws/voice/{call_id}"
    status_url = f"{base}/api/twilio/status/{call_id}"

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        # Say a brief greeting while the WebSocket pipeline warms up
        '<Say voice="Polly.Aditi" language="en-IN">'
        f"Welcome to {settings.RESTAURANT_NAME}. Please hold for a moment."
        "</Say>"
        "<Connect>"
        f'<Stream url="{stream_url}">'
        # Pass caller phone as a custom parameter into the WebSocket handler
        f'<Parameter name="from_number" value="{customer_phone}"/>'
        "</Stream>"
        "</Connect>"
        "</Response>"
    )


@router.post("/incoming")
async def handle_incoming_call(
    request: Request,
    From: Optional[str] = Form(None),
    CallSid: Optional[str] = Form(None),
):
    """
    Twilio calls this when a customer dials the restaurant number.
    Returns <Connect><Stream> TwiML → pipecat pipeline handles the call.
    """
    customer_phone = From or "unknown"
    call_id = CallSid or str(uuid.uuid4())

    logger.info(f"Incoming call from {customer_phone} (call_id={call_id})")

    # Pre-create customer record (non-blocking)
    try:
        await ensure_customer_record(customer_phone)
    except Exception:
        pass

    twiml = _stream_twiml(call_id=call_id, customer_phone=customer_phone)
    return Response(content=twiml, media_type="application/xml")


@router.post("/status/{call_id}")
async def call_status_callback(
    call_id: str,
    CallStatus: Optional[str] = Form(None),
    CallDuration: Optional[str] = Form(None),
):
    """Twilio status callback – fired when the call ends."""
    duration = int(CallDuration) if CallDuration and CallDuration.isdigit() else None
    if CallStatus in ("completed", "failed", "busy", "no-answer"):
        try:
            await end_call_log(call_id=call_id, duration_seconds=duration)
        except Exception:
            pass
    return PlainTextResponse("OK")

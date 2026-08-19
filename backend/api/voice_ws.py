"""
WebSocket endpoint for Twilio Media Streams.

Twilio connects here when a call is answered and streams raw audio
bidirectionally. Pipecat runs the full STT→LLM→TTS pipeline per connection.
"""
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.conversation_service import start_call_log, end_call_log
from backend.voice.pipeline import run_voice_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["Voice WebSocket"])


@router.websocket("/voice/{call_id}")
async def voice_stream(websocket: WebSocket, call_id: str):
    """
    Twilio Media Stream WebSocket.
    One connection = one phone call.
    """
    await websocket.accept()

    # Extract caller phone from the Twilio 'start' event
    customer_phone = "unknown"
    try:
        import json
        first_msg = await websocket.receive_text()
        data = json.loads(first_msg)
        if data.get("event") == "start":
            customer_phone = (
                data.get("start", {})
                    .get("customParameters", {})
                    .get("from_number", "unknown")
            )
    except Exception:
        pass

    logger.info(f"Voice stream started: call_id={call_id} phone={customer_phone}")
    await start_call_log(call_id=call_id, customer_phone=customer_phone, twilio_sid=call_id)

    try:
        await run_voice_pipeline(
            websocket=websocket,
            call_id=call_id,
            customer_phone=customer_phone,
        )
    except WebSocketDisconnect:
        logger.info(f"[{call_id}] WebSocket disconnected normally")
    except Exception as e:
        logger.error(f"[{call_id}] Pipeline error: {e}", exc_info=True)
    finally:
        await end_call_log(call_id=call_id)
        logger.info(f"[{call_id}] Voice stream ended")

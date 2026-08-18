"""
Twilio webhook endpoints – the voice call entry point.
Handles inbound call setup and speech input turns.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import PlainTextResponse

from backend.config import settings
from backend.telephony.twilio_service import twilio_provider
from backend.agent.graph import run_agent_turn
from backend.agent.memory import load_customer_context, ensure_customer_record
from backend.services.conversation_service import (
    start_call_log,
    end_call_log,
    save_message,
)
from backend.services.sarvam_tts import sarvam_tts

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twilio", tags=["Telephony"])


def _build_action_url(call_id: str) -> str:
    base = settings.TWILIO_WEBHOOK_BASE_URL.rstrip("/")
    return f"{base}/api/twilio/speech/{call_id}"


@router.post("/incoming")
async def handle_incoming_call(
    request: Request,
    From: Optional[str] = Form(None),
    CallSid: Optional[str] = Form(None),
):
    """
    Twilio calls this endpoint when a customer dials the restaurant number.
    We generate a greeting TwiML and begin the conversation.
    """
    customer_phone = From or "unknown"
    call_id = CallSid or str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    logger.info(f"Incoming call from {customer_phone} (call_id={call_id})")

    # Persist call record
    await start_call_log(call_id=call_id, customer_phone=customer_phone, twilio_sid=CallSid)
    await ensure_customer_record(customer_phone)

    # Build action URL for the speech gather
    action_url = _build_action_url(call_id)

    # Generate greeting TwiML
    twiml = twilio_provider.generate_initial_greeting(action_url=action_url)
    return Response(content=twiml, media_type="application/xml")


@router.post("/speech/{call_id}")
async def handle_speech_input(
    call_id: str,
    request: Request,
    From: Optional[str] = Form(None),
    SpeechResult: Optional[str] = Form(None),
    CallStatus: Optional[str] = Form(None),
):
    """
    Twilio posts here after each Gather completes with the speech result.
    We run the agent and return TwiML with the AI response.
    """
    customer_phone = From or "unknown"
    user_input = (SpeechResult or "").strip()

    logger.info(f"Speech input [{call_id}]: {user_input!r}")

    # Handle call completed/failed status
    if CallStatus in ("completed", "failed", "busy", "no-answer"):
        await end_call_log(call_id=call_id)
        return Response(content=twilio_provider.generate_hangup(), media_type="application/xml")

    if not user_input:
        # No speech detected; prompt again
        action_url = _build_action_url(call_id)
        twiml = twilio_provider.generate_voice_response(
            text="I didn't quite catch that. Could you please repeat?",
            gather_speech=True,
            action_url=action_url,
        )
        return Response(content=twiml, media_type="application/xml")

    # Save customer utterance
    await save_message(call_id, customer_phone, "user", user_input)

    # Load customer context for first turn
    context = await load_customer_context(customer_phone)

    # Run agent
    try:
        result = await run_agent_turn(
            call_id=call_id,
            session_id=call_id,  # Use call_id as LangGraph thread_id
            customer_phone=customer_phone,
            user_input=user_input,
            state_override=context,
        )
        agent_response = result.get("agent_response") or "I'm having trouble right now. Please try again."
        should_end = result.get("should_end", False)
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        agent_response = "I'm experiencing a technical issue. Please call back shortly."
        should_end = False

    # Save agent response
    await save_message(call_id, customer_phone, "assistant", agent_response)

    if should_end:
        # End conversation
        await end_call_log(call_id=call_id)
        twiml_content = twilio_provider.generate_voice_response(
            text=agent_response,
            gather_speech=False,
        )
        response = Response(content=twiml_content, media_type="application/xml")
        return response

    # Continue conversation
    action_url = _build_action_url(call_id)

    # Try Sarvam TTS for natural voice; fall back to Twilio built-in TTS
    audio_bytes = await sarvam_tts.synthesize(agent_response)
    audio_url: Optional[str] = None
    if audio_bytes:
        # In production, upload audio_bytes to a CDN / S3 and use the URL.
        # For now, we fall back to Twilio's TTS engine.
        audio_url = None  # TODO: implement audio hosting

    twiml_content = twilio_provider.generate_voice_response(
        text=agent_response,
        audio_url=audio_url,
        gather_speech=True,
        action_url=action_url,
    )
    return Response(content=twiml_content, media_type="application/xml")


@router.post("/status/{call_id}")
async def call_status_callback(
    call_id: str,
    CallStatus: Optional[str] = Form(None),
    CallDuration: Optional[str] = Form(None),
):
    """Twilio status callback to update call log when the call ends."""
    duration = int(CallDuration) if CallDuration and CallDuration.isdigit() else None
    if CallStatus in ("completed", "failed", "busy", "no-answer"):
        await end_call_log(call_id=call_id, duration_seconds=duration)
    return PlainTextResponse("OK")

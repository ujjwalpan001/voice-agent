"""
Real-time voice pipeline using Pipecat 0.0.108.

Architecture per call:
  Twilio WebSocket (raw mulaw audio)
    ↓ FastAPIWebsocketTransport (input)
    ↓ SileroVAD (end-of-turn detection)
    ↓ SarvamSTT (speech → text)
    ↓ LLMUserContextAggregator (transcript → messages frame)
    ↓ GroqLLMService (LLM inference)
    ↓ LLMAssistantContextAggregator (stores reply)
    ↓ SarvamTTS (text → streaming audio via WebSocket)
    ↓ FastAPIWebsocketTransport (output back to Twilio)

Result: continuous bidirectional audio with ~700ms turn latency
instead of the 2-4s round-trip of the old <Gather> polling approach.
"""
import logging

from fastapi import WebSocket

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import EndFrame, LLMMessagesFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.aggregators.llm_response import (
    LLMUserContextAggregator,
    LLMAssistantContextAggregator,
)
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from backend.agent.prompts import SYSTEM_PROMPT
from backend.config import settings

logger = logging.getLogger(__name__)


def _build_system_prompt(customer_phone: str) -> str:
    """Inject restaurant name and caller phone into the system prompt."""
    prompt = SYSTEM_PROMPT
    try:
        prompt = prompt.format(
            restaurant_name=settings.RESTAURANT_NAME,
            customer_phone=customer_phone,
        )
    except (KeyError, IndexError):
        pass
    return prompt


async def run_voice_pipeline(
    websocket: WebSocket,
    call_id: str,
    customer_phone: str,
) -> None:
    """
    Build and run the full pipecat pipeline for one phone call.
    Blocks until the call ends (WebSocket closes or EndFrame received).
    """

    # ── Transport ────────────────────────────────────────────────────────────
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(stop_secs=0.7)   # 700 ms silence = user done speaking
            ),
            vad_audio_passthrough=True,
            session_timeout=1800,  # 30-min max call
        ),
    )

    # ── STT ──────────────────────────────────────────────────────────────────
    stt = SarvamSTTService(
        api_key=settings.SARVAM_API_KEY,
        settings=SarvamSTTService.Settings(model="saarika:v2.5"),
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm = GroqLLMService(
        api_key=settings.GROQ_API_KEY,
        settings=GroqLLMService.Settings(model=settings.GROQ_MODEL),
    )

    # ── TTS ──────────────────────────────────────────────────────────────────
    tts = SarvamTTSService(
        api_key=settings.SARVAM_API_KEY,
        settings=SarvamTTSService.Settings(
            model="bulbul:v2",
            language=settings.SARVAM_LANGUAGE,
            voice=settings.SARVAM_TTS_VOICE,
        ),
        sample_rate=8000,  # Match Twilio's 8 kHz mulaw stream
    )

    # ── Conversation context ──────────────────────────────────────────────────
    messages = [
        {"role": "system", "content": _build_system_prompt(customer_phone)}
    ]
    context = OpenAILLMContext(messages=messages)
    context.set_llm_adapter(llm.get_llm_adapter())

    user_aggregator = LLMUserContextAggregator(context)
    assistant_aggregator = LLMAssistantContextAggregator(context)

    # ── Pipeline ─────────────────────────────────────────────────────────────
    pipeline = Pipeline(
        [
            transport.input(),      # Raw audio in from Twilio WebSocket
            stt,                    # Audio → transcript text
            user_aggregator,        # Transcript → OpenAI-format messages frame
            llm,                    # Messages → LLM token stream
            tts,                    # Token stream → audio chunks (streaming WS)
            transport.output(),     # Audio chunks → Twilio WebSocket
            assistant_aggregator,   # Store assistant reply in context memory
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,       # User can interrupt bot mid-sentence
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    # ── Lifecycle hooks ───────────────────────────────────────────────────────
    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        logger.info(f"[{call_id}] Pipecat pipeline connected")

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(transport, client):
        logger.info(f"[{call_id}] Pipecat pipeline disconnected")
        await task.queue_frames([EndFrame()])

    # ── Run (blocks until call ends) ──────────────────────────────────────────
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)

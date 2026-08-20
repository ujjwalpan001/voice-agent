"""
Real-time voice pipeline using Pipecat 0.0.108 and LangGraph.

Architecture per call:
  Twilio WebSocket (raw mulaw audio)
    ↓ FastAPIWebsocketTransport (input)
    ↓ SileroVAD (end-of-turn detection)
    ↓ SarvamSTT (speech → text)
    ↓ LangGraphAgentProcessor (runs the LangGraph agent turn, fetches DB/tools)
    ↓ SarvamTTS (text → streaming audio via WebSocket)
    ↓ FastAPIWebsocketTransport (output back to Twilio)
"""
import logging
from fastapi import WebSocket

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    TextFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    EndFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from backend.config import settings
from backend.agent.graph import run_agent_turn

logger = logging.getLogger(__name__)


# ─── LangGraph Agent Bridge Processor ─────────────────────────────────────────

class LangGraphAgentProcessor(FrameProcessor):
    """
    Bridges Pipecat's frame-based voice loop with the compiled LangGraph agent.
    Intercepts transcribed text frames, runs the state graph turn (DB, cart, RAG),
    and pushes natural language response text downstream.
    """
    def __init__(self, call_id: str, session_id: str, customer_phone: str):
        super().__init__()
        self.call_id = call_id
        self.session_id = session_id
        self.customer_phone = customer_phone

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        
        if isinstance(frame, TranscriptionFrame):
            user_text = frame.text.strip()
            if not user_text:
                await self.push_frame(frame, direction)
                return
                
            logger.info(f"[{self.call_id}] Processing turn through LangGraph agent for user speech: '{user_text}'")
            try:
                # Execute turn in LangGraph graph (database writes and tools are run inside the nodes)
                result = await run_agent_turn(
                    call_id=self.call_id,
                    session_id=self.session_id,
                    customer_phone=self.customer_phone,
                    user_input=user_text
                )
                import re
                response_text = result.get("agent_response", "")
                
                # Strip out any <think>...</think> blocks and their content (common in Qwen/reasoning models)
                response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL | re.IGNORECASE)
                response_text = re.sub(r'<think>.*', '', response_text, flags=re.DOTALL | re.IGNORECASE)
                response_text = response_text.strip()
                
                should_end = result.get("should_end", False)
                
                # Push start of response
                await self.push_frame(LLMFullResponseStartFrame(), direction)
                
                # Push the agent's natural text response downstream to TTS
                await self.push_frame(TextFrame(response_text), direction)
                
                # Push end of response
                await self.push_frame(LLMFullResponseEndFrame(), direction)
                
                if should_end:
                    logger.info(f"[{self.call_id}] Agent requested call termination. Hanging up.")
                    await self.push_frame(EndFrame(), direction)
                    
            except Exception as e:
                logger.error(f"[{self.call_id}] Error in LangGraph turn execution: {e}", exc_info=True)
                await self.push_frame(LLMFullResponseStartFrame(), direction)
                await self.push_frame(TextFrame("Sorry, I had trouble processing that. Could you repeat?"), direction)
                await self.push_frame(LLMFullResponseEndFrame(), direction)
        else:
            await self.push_frame(frame, direction)


# ─── Production Voice Pipeline Runner ─────────────────────────────────────────

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

    # ── LangGraph Agent Processor ─────────────────────────────────────────────
    agent_processor = LangGraphAgentProcessor(
        call_id=call_id,
        session_id=call_id,
        customer_phone=customer_phone,
    )

    # ── Pipeline ─────────────────────────────────────────────────────────────
    pipeline = Pipeline(
        [
            transport.input(),      # Raw audio in from Twilio WebSocket
            stt,                    # Audio → transcript text
            agent_processor,        # Intercepts text, executes LangGraph turn, outputs response text
            tts,                    # Response text → audio chunks (streaming WS)
            transport.output(),     # Audio chunks → Twilio WebSocket
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

"""
Sarvam AI Text-to-Speech service.
Returns audio bytes for streaming back to Twilio.
"""
import httpx
import base64
import logging
from typing import Optional, AsyncIterator
from backend.config import settings

logger = logging.getLogger(__name__)

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"


class SarvamTTSService:
    """
    Wrapper around Sarvam AI TTS API.
    Converts agent text responses to speech audio.
    """

    def __init__(self):
        self.api_key = settings.SARVAM_API_KEY
        self.model = settings.SARVAM_TTS_MODEL
        self.speaker = settings.SARVAM_TTS_VOICE
        self.language = settings.SARVAM_LANGUAGE
        self.headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def synthesize(
        self,
        text: str,
        language_code: Optional[str] = None,
        speaker: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 0.0,
    ) -> Optional[bytes]:
        """
        Convert text to speech audio.

        Args:
            text: The text to synthesize.
            language_code: BCP-47 code (e.g. 'en-IN', 'hi-IN').
            speaker: TTS speaker voice name.
            speed: Playback speed (0.5 – 2.0).
            pitch: Voice pitch adjustment.

        Returns:
            Raw WAV audio bytes or None on failure.
        """
        payload = {
            "inputs": [text],
            "target_language_code": language_code or self.language,
            "speaker": speaker or self.speaker,
            "model": self.model,
            "pitch": pitch,
            "pace": speed,
            "loudness": 1.0,
            "speech_sample_rate": 8000,   # 8kHz for Twilio µ-law
            "enable_preprocessing": True,
            "eng_interpolation_wt": 123,  # code-mixed weight
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    SARVAM_TTS_URL,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                # Sarvam returns base64-encoded audio per input chunk
                audios = result.get("audios", [])
                if not audios:
                    logger.warning("Sarvam TTS returned empty audios list.")
                    return None
                audio_b64 = audios[0]
                audio_bytes = base64.b64decode(audio_b64)
                logger.debug(f"TTS synthesized {len(audio_bytes)} bytes for text: {text[:60]!r}")
                return audio_bytes
        except httpx.HTTPStatusError as e:
            logger.error(f"Sarvam TTS HTTP error {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Sarvam TTS error: {e}")
            return None

    async def synthesize_chunked(
        self,
        text: str,
        chunk_size: int = 200,
        language_code: Optional[str] = None,
        speaker: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        Synthesize long text by splitting into sentence chunks and
        yielding audio bytes as they arrive for lower perceived latency.
        """
        import re
        sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
        buffer = ""
        for sentence in sentences:
            buffer += " " + sentence
            if len(buffer) >= chunk_size:
                audio = await self.synthesize(buffer.strip(), language_code, speaker)
                if audio:
                    yield audio
                buffer = ""
        if buffer.strip():
            audio = await self.synthesize(buffer.strip(), language_code, speaker)
            if audio:
                yield audio


# Singleton
sarvam_tts = SarvamTTSService()

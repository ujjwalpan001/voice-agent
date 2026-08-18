"""
Sarvam AI Speech-to-Text service.
Supports real-time transcription with Indian language support.
"""
import httpx
import logging
import io
from typing import Optional
from backend.config import settings

logger = logging.getLogger(__name__)

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_STT_TRANSLATE_URL = "https://api.sarvam.ai/speech-to-text-translate"


class SarvamSTTService:
    """
    Wrapper around Sarvam AI Speech-to-Text API.
    Handles audio transcription for Indian languages and code-mixed speech.
    """

    def __init__(self):
        self.api_key = settings.SARVAM_API_KEY
        self.model = settings.SARVAM_STT_MODEL
        self.language = settings.SARVAM_LANGUAGE
        self.headers = {
            "api-subscription-key": self.api_key,
        }

    async def transcribe(
        self,
        audio_data: bytes,
        language_code: Optional[str] = None,
        audio_format: str = "wav",
    ) -> Optional[str]:
        """
        Transcribe raw audio bytes to text.

        Args:
            audio_data: Raw audio bytes (WAV / PCM preferred)
            language_code: BCP-47 language code (e.g. 'hi-IN', 'te-IN', 'en-IN')
                           Defaults to settings.SARVAM_LANGUAGE
            audio_format: Audio format hint (wav, mp3, etc.)

        Returns:
            Transcribed text string or None on failure.
        """
        lang = language_code or self.language
        files = {
            "file": (f"audio.{audio_format}", io.BytesIO(audio_data), f"audio/{audio_format}"),
        }
        data = {
            "model": self.model,
            "language_code": lang,
            "with_timestamps": "false",
            "with_diarisation": "false",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    SARVAM_STT_URL,
                    headers=self.headers,
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                result = response.json()
                transcript = result.get("transcript", "").strip()
                logger.debug(f"STT transcript: {transcript!r}")
                return transcript if transcript else None
        except httpx.HTTPStatusError as e:
            logger.error(f"Sarvam STT HTTP error {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Sarvam STT error: {e}")
            return None

    async def transcribe_and_translate(
        self,
        audio_data: bytes,
        language_code: Optional[str] = None,
        audio_format: str = "wav",
    ) -> Optional[str]:
        """
        Transcribe non-English audio and translate it to English.
        Useful when the agent processes mixed or regional-language inputs.
        """
        lang = language_code or self.language
        files = {
            "file": (f"audio.{audio_format}", io.BytesIO(audio_data), f"audio/{audio_format}"),
        }
        data = {
            "model": self.model,
            "language_code": lang,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    SARVAM_STT_TRANSLATE_URL,
                    headers=self.headers,
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                result = response.json()
                transcript = result.get("transcript", "").strip()
                logger.debug(f"STT (translate) transcript: {transcript!r}")
                return transcript if transcript else None
        except httpx.HTTPStatusError as e:
            logger.error(f"Sarvam STT-translate HTTP error {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Sarvam STT-translate error: {e}")
            return None


# Singleton
sarvam_stt = SarvamSTTService()

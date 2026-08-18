"""
Twilio telephony provider implementation.
Handles incoming calls, webhook validation, and TwiML response generation.
"""
import base64
import hashlib
import hmac
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.request_validator import RequestValidator

from backend.config import settings
from backend.telephony.base import TelephonyProvider

logger = logging.getLogger(__name__)


class TwilioProvider(TelephonyProvider):
    """Twilio implementation of the telephony provider interface."""

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        self._validator = RequestValidator(self.auth_token) if self.auth_token else None

    def generate_voice_response(
        self,
        text: str,
        audio_url: Optional[str] = None,
        gather_speech: bool = True,
        action_url: Optional[str] = None,
    ) -> str:
        """
        Generate TwiML that plays text-to-speech and optionally gathers input.

        Args:
            text: Text to say (or fallback if audio_url provided).
            audio_url: URL of pre-rendered audio (from Sarvam TTS).
            gather_speech: If True, collect the caller's next utterance.
            action_url: Webhook URL for the gathered speech.

        Returns:
            TwiML XML string.
        """
        response = VoiceResponse()
        if gather_speech and action_url:
            gather = Gather(
                input="speech",
                action=action_url,
                method="POST",
                speech_timeout="auto",
                language="en-IN",
            )
            if audio_url:
                gather.play(audio_url)
            else:
                gather.say(text, voice="Polly.Aditi", language="en-IN")
            response.append(gather)
            # Fallback if no speech detected
            response.say("I didn't hear anything. Please call again.", voice="Polly.Aditi")
        else:
            if audio_url:
                response.play(audio_url)
            else:
                response.say(text, voice="Polly.Aditi", language="en-IN")

        return str(response)

    def generate_initial_greeting(self, action_url: str) -> str:
        """Generate the opening TwiML greeting with speech gather."""
        response = VoiceResponse()
        gather = Gather(
            input="speech",
            action=action_url,
            method="POST",
            speech_timeout="auto",
            language="en-IN",
        )
        gather.say(
            f"Welcome to {settings.RESTAURANT_NAME}! "
            "I'm your AI assistant. How can I help you today? "
            "You can tell me what you'd like to order.",
            voice="Polly.Aditi",
            language="en-IN",
        )
        response.append(gather)
        return str(response)

    def validate_webhook(
        self,
        request_data: Dict[str, Any],
        signature: str,
        url: str,
    ) -> bool:
        """Validate Twilio webhook signature."""
        if not self._validator:
            logger.warning("Twilio webhook validation skipped (no auth token configured).")
            return True
        return self._validator.validate(url, request_data, signature)

    def get_caller_phone(self, webhook_data: Dict[str, Any]) -> Optional[str]:
        return webhook_data.get("From")

    def get_call_sid(self, webhook_data: Dict[str, Any]) -> Optional[str]:
        return webhook_data.get("CallSid")

    def get_speech_result(self, webhook_data: Dict[str, Any]) -> Optional[str]:
        """Extract the transcribed speech result from a Twilio Gather webhook."""
        return webhook_data.get("SpeechResult")

    def generate_hangup(self) -> str:
        """Generate TwiML to hang up the call."""
        response = VoiceResponse()
        response.hangup()
        return str(response)


# Singleton
twilio_provider = TwilioProvider()

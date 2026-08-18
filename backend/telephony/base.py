"""
Abstract telephony provider interface.
Swap Twilio for another provider by implementing this base class.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class TelephonyProvider(ABC):
    """Base class for telephony integrations."""

    @abstractmethod
    def generate_voice_response(self, text: str, audio_url: Optional[str] = None) -> str:
        """
        Generate a provider-specific response (e.g. TwiML XML) that speaks text.
        """
        ...

    @abstractmethod
    def validate_webhook(self, request_data: Dict[str, Any], signature: str, url: str) -> bool:
        """Validate that an incoming webhook is genuine."""
        ...

    @abstractmethod
    def get_caller_phone(self, webhook_data: Dict[str, Any]) -> Optional[str]:
        """Extract the caller's phone number from webhook payload."""
        ...

    @abstractmethod
    def get_call_sid(self, webhook_data: Dict[str, Any]) -> Optional[str]:
        """Extract the unique call SID from webhook payload."""
        ...

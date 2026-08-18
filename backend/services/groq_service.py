"""
Groq LLM service – fast inference for conversational voice agents.
Supports streaming and function/tool calling.
"""
import logging
from typing import Optional, List, Dict, Any, AsyncIterator
from backend.config import settings

logger = logging.getLogger(__name__)


class GroqService:
    """Async wrapper around Groq's Chat Completions API. Client is lazily initialised."""

    def __init__(self):
        self._client = None  # Lazy init – avoids httpx/groq compat issues at import time

    def _get_client(self):
        if self._client is None:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        return self._client

    @property
    def model(self) -> str:
        return settings.GROQ_MODEL

    @property
    def max_tokens(self) -> int:
        return settings.GROQ_MAX_TOKENS

    @property
    def temperature(self) -> float:
        return settings.GROQ_TEMPERATURE

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Non-streaming chat completion with optional tool calling.

        Returns:
            Full Groq response object.
        """
        kwargs: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            response = await self._get_client().chat.completions.create(**kwargs)
            return response
        except Exception as e:
            logger.error(f"Groq chat error: {e}")
            raise

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Streaming chat – yields text delta chunks.
        Tool calling is not available in streaming mode; use chat() for tools.
        """
        try:
            stream = await self._get_client().chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as e:
            logger.error(f"Groq stream error: {e}")
            raise

    def extract_text(self, response) -> str:
        """Extract text content from a Groq response object."""
        try:
            return response.choices[0].message.content or ""
        except (IndexError, AttributeError):
            return ""

    def extract_tool_calls(self, response) -> List[Dict[str, Any]]:
        """Extract tool call information from a Groq response."""
        try:
            tool_calls = response.choices[0].message.tool_calls
            if not tool_calls:
                return []
            result = []
            for tc in tool_calls:
                result.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })
            return result
        except (IndexError, AttributeError):
            return []


# Singleton
groq_service = GroqService()

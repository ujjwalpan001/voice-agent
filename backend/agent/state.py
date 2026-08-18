"""
LangGraph agent state definition.
The state flows through every node in the restaurant ordering graph.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Shared state carried through the entire agent graph."""

    # ─── Call / Session ──────────────────────────────────────────────────────
    call_id: str
    session_id: str
    customer_phone: str

    # ─── Customer ────────────────────────────────────────────────────────────
    customer_name: Optional[str]
    customer_memory: Optional[str]   # Formatted long-term memory string

    # ─── Conversation ────────────────────────────────────────────────────────
    # `messages` uses add_messages reducer so concurrent updates merge cleanly.
    messages: Annotated[List[Dict[str, Any]], add_messages]
    user_input: str                  # Latest raw transcript from STT

    # ─── Context ─────────────────────────────────────────────────────────────
    retrieved_context: Optional[str]   # RAG results formatted as text
    current_intent: Optional[str]      # e.g. "menu_search", "add_to_cart"

    # ─── Cart & Order ────────────────────────────────────────────────────────
    current_cart: Optional[Dict[str, Any]]
    order_state: Optional[str]          # "pending", "confirmed", etc.
    order_id: Optional[str]

    # ─── Delivery ────────────────────────────────────────────────────────────
    delivery_info: Optional[Dict[str, Any]]

    # ─── Billing ─────────────────────────────────────────────────────────────
    billing_info: Optional[Dict[str, Any]]

    # ─── Agent response ──────────────────────────────────────────────────────
    agent_response: Optional[str]      # Final text to be passed to TTS
    should_end: bool                   # Signal to terminate the call

    # ─── Tool results (transient) ────────────────────────────────────────────
    tool_results: Optional[Dict[str, Any]]

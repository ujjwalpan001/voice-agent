"""
LangGraph agent graph definition.
Assembles all nodes, edges, and routing logic into a compiled graph.
"""
from __future__ import annotations
import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from backend.agent.state import AgentState
from backend.agent.nodes import (
    load_session_node,
    intent_detection_node,
    rag_retrieval_node,
    menu_search_node,
    cart_management_node,
    billing_node,
    collect_info_node,
    order_confirmation_node,
    order_status_node,
    generate_response_node,
    end_call_node,
)
from backend.agent.routers.intent_router import route_by_intent, should_end

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Construct and compile the restaurant ordering agent graph."""
    builder = StateGraph(AgentState)

    # ─── Nodes ───────────────────────────────────────────────────────────────
    builder.add_node("load_session", load_session_node)
    builder.add_node("intent_detection", intent_detection_node)
    builder.add_node("rag_retrieval", rag_retrieval_node)
    builder.add_node("menu_search", menu_search_node)
    builder.add_node("cart_management", cart_management_node)
    builder.add_node("billing_node", billing_node)
    builder.add_node("collect_info", collect_info_node)
    builder.add_node("order_confirmation", order_confirmation_node)
    builder.add_node("order_status", order_status_node)
    builder.add_node("generate_response", generate_response_node)
    builder.add_node("end_call", end_call_node)

    # ─── Entry point ─────────────────────────────────────────────────────────
    builder.set_entry_point("load_session")

    # ─── Edges ───────────────────────────────────────────────────────────────
    builder.add_edge("load_session", "intent_detection")

    # After intent detection → route dynamically
    builder.add_conditional_edges(
        "intent_detection",
        route_by_intent,
        {
            "rag_retrieval": "rag_retrieval",
            "menu_search": "menu_search",
            "cart_management": "cart_management",
            "billing_node": "billing_node",
            "collect_info": "collect_info",
            "order_confirmation": "order_confirmation",
            "order_status": "order_status",
            "generate_response": "generate_response",
            "end_call": "end_call",
        },
    )

    # After RAG retrieval → generate final response
    builder.add_edge("rag_retrieval", "generate_response")

    # All response generators → check if call should end
    for terminal_node in [
        "menu_search",
        "cart_management",
        "billing_node",
        "collect_info",
        "order_confirmation",
        "order_status",
        "generate_response",
    ]:
        builder.add_edge(terminal_node, END)

    builder.add_edge("end_call", END)

    # ─── Compile with in-memory checkpointing ────────────────────────────────
    memory_saver = MemorySaver()
    compiled = builder.compile(checkpointer=memory_saver)
    logger.info("Restaurant agent graph compiled successfully.")
    return compiled


# Pre-built singleton graph
restaurant_graph = build_graph()


async def run_agent_turn(
    call_id: str,
    session_id: str,
    customer_phone: str,
    user_input: str,
    state_override: dict = None,
) -> dict:
    """
    Process a single conversation turn through the agent graph.

    Args:
        call_id: Unique call identifier.
        session_id: Conversation/session ID (used as LangGraph thread ID).
        customer_phone: Caller's phone number.
        user_input: Transcribed speech text.
        state_override: Additional state fields to merge.

    Returns:
        Updated state dict with 'agent_response' populated.
    """
    config = {"configurable": {"thread_id": session_id}}

    input_state: AgentState = {
        "call_id": call_id,
        "session_id": session_id,
        "customer_phone": customer_phone,
        "user_input": user_input,
        "messages": [{"role": "user", "content": user_input}],
        "customer_name": None,
        "customer_memory": None,
        "retrieved_context": None,
        "current_intent": None,
        "current_cart": None,
        "order_state": None,
        "order_id": None,
        "delivery_info": None,
        "billing_info": None,
        "agent_response": None,
        "should_end": False,
        "tool_results": None,
        **(state_override or {}),
    }

    result = await restaurant_graph.ainvoke(input_state, config=config)
    return result

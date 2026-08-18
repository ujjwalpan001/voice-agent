"""
LangGraph routing functions.
Each router inspects the current state and returns the name of the next node.
"""
from __future__ import annotations
from backend.agent.state import AgentState

# Intent → node mapping
INTENT_TO_NODE = {
    "greeting": "generate_response",
    "menu_search": "rag_retrieval",
    "category_browse": "menu_search",
    "add_to_cart": "cart_management",
    "remove_from_cart": "cart_management",
    "update_quantity": "cart_management",
    "view_cart": "cart_management",
    "bill_inquiry": "billing_node",
    "delivery_info": "collect_info",
    "confirm_order": "order_confirmation",
    "cancel_order": "order_confirmation",
    "order_status": "order_status",
    "restaurant_info": "rag_retrieval",
    "complaint": "generate_response",
    "farewell": "end_call",
    "other": "generate_response",
}


def route_by_intent(state: AgentState) -> str:
    """Route to a node based on the detected intent."""
    intent = state.get("current_intent", "other")
    return INTENT_TO_NODE.get(intent, "generate_response")


def should_end(state: AgentState) -> str:
    """Terminal check: route to END or back to intent detection."""
    if state.get("should_end", False):
        return "END"
    return "intent_detection"

"""
LangGraph nodes for the restaurant voice agent.
Each node is an async function that accepts and returns AgentState.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Dict, Optional

from backend.agent.state import AgentState
from backend.agent.prompts import (
    SYSTEM_PROMPT,
    INTENT_DETECTION_PROMPT,
    RAG_SYNTHESIS_PROMPT,
)
from backend.config import settings
from backend.services.groq_service import groq_service
from backend.rag.retrieval import rag_service
from backend.tools.menu_tools import (
    search_menu,
    get_items_by_category,
    get_all_categories,
    format_menu_items_for_voice,
)
from backend.tools.cart_tools import (
    get_cart,
    add_to_cart,
    remove_from_cart,
    update_cart_quantity,
    clear_cart,
    format_cart_for_voice,
)
from backend.tools.order_tools import (
    create_order_from_cart,
    get_orders_by_phone,
    format_order_for_voice,
)
from backend.tools.billing_tools import get_bill_preview, format_bill_for_voice
from backend.tools.customer_tools import upsert_customer

logger = logging.getLogger(__name__)


# ─── Helper ───────────────────────────────────────────────────────────────────

def _build_system_prompt(state: AgentState) -> str:
    return SYSTEM_PROMPT.format(
        restaurant_name=settings.RESTAURANT_NAME,
        customer_memory=state.get("customer_memory") or "No previous history.",
    )


# ─── Node: Load Session ───────────────────────────────────────────────────────

async def load_session_node(state: AgentState) -> AgentState:
    """Initialise session state (called once per call)."""
    phone = state["customer_phone"]
    await upsert_customer(phone)
    return state


# ─── Node: Intent Detection ───────────────────────────────────────────────────

async def intent_detection_node(state: AgentState) -> AgentState:
    """Classify the user's intent using a lightweight LLM call."""
    user_input = state.get("user_input", "")
    cart = state.get("current_cart") or {}
    cart_items = cart.get("items", [])
    cart_summary = format_cart_for_voice(cart) if cart_items else "empty"

    prompt = INTENT_DETECTION_PROMPT.format(
        user_input=user_input,
        cart_summary=cart_summary,
    )
    response = await groq_service.chat(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",   # Fast model for classification
    )
    intent = groq_service.extract_text(response).strip().lower()
    # Sanitise
    valid_intents = {
        "greeting", "menu_search", "category_browse", "add_to_cart",
        "remove_from_cart", "update_quantity", "view_cart", "bill_inquiry",
        "delivery_info", "confirm_order", "cancel_order", "order_status",
        "restaurant_info", "complaint", "farewell", "other",
    }
    if intent not in valid_intents:
        intent = "other"
    logger.debug(f"Intent detected: {intent!r} for input: {user_input!r}")
    return {**state, "current_intent": intent}


# ─── Node: RAG Retrieval ──────────────────────────────────────────────────────

async def rag_retrieval_node(state: AgentState) -> AgentState:
    """Retrieve relevant restaurant knowledge for the user's query."""
    query = state.get("user_input", "")
    context = rag_service.retrieve_formatted(query, n_results=5)
    return {**state, "retrieved_context": context}


# ─── Node: Menu Search ────────────────────────────────────────────────────────

async def menu_search_node(state: AgentState) -> AgentState:
    """Search menu items and format for voice response."""
    query = state.get("user_input", "")
    items = await search_menu(query, limit=5)
    if not items:
        # Try category list
        categories = await get_all_categories()
        response = (
            f"I couldn't find '{query}' on our menu. "
            f"We have these categories: {', '.join(categories[:6])}. "
            "What would you like?"
        )
    else:
        response = "Here's what I found: " + format_menu_items_for_voice(items)
    return {**state, "agent_response": response}


# ─── Node: Cart Management ───────────────────────────────────────────────────

async def cart_management_node(state: AgentState) -> AgentState:
    """
    Handle add / remove / update / view cart operations.
    The LLM interprets the request and calls the appropriate tool.
    """
    intent = state.get("current_intent", "view_cart")
    call_id = state["call_id"]
    phone = state["customer_phone"]
    user_input = state.get("user_input", "")

    # Refresh cart
    cart = await get_cart(call_id)

    if intent == "view_cart":
        response = format_cart_for_voice(cart or {})
        return {**state, "current_cart": cart, "agent_response": response}

    # For add/remove/update, use the LLM with tools to determine exact action
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_and_add_to_cart",
                "description": "Search for a menu item by name and add it to cart",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_name": {"type": "string"},
                        "quantity": {"type": "integer", "default": 1},
                        "special_instructions": {"type": "string"},
                    },
                    "required": ["item_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "remove_item_from_cart",
                "description": "Remove an item from the cart by name",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_name": {"type": "string"},
                    },
                    "required": ["item_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_item_quantity",
                "description": "Update the quantity of a cart item",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_name": {"type": "string"},
                        "quantity": {"type": "integer"},
                    },
                    "required": ["item_name", "quantity"],
                },
            },
        },
    ]

    messages = [
        {"role": "system", "content": _build_system_prompt(state)},
        *state.get("messages", []),
        {"role": "user", "content": user_input},
    ]

    response_obj = await groq_service.chat(messages=messages, tools=tools)
    tool_calls = groq_service.extract_tool_calls(response_obj)

    agent_response = ""
    for tc in tool_calls:
        args = json.loads(tc["arguments"])
        name = tc["name"]

        if name == "search_and_add_to_cart":
            item_name = args["item_name"]
            qty = args.get("quantity", 1)
            instructions = args.get("special_instructions")

            # Find item in DB
            from backend.tools.menu_tools import get_menu_item_by_name
            item = await get_menu_item_by_name(item_name)
            if item:
                result = await add_to_cart(call_id, phone, item["id"], qty, instructions)
                if result["success"]:
                    agent_response += f"Added {qty}x {item['name']} to your cart. "
                else:
                    agent_response += f"Sorry, I couldn't add {item_name}: {result.get('error')}. "
            else:
                agent_response += f"Sorry, I couldn't find {item_name} on the menu. "

        elif name == "remove_item_from_cart":
            item_name = args["item_name"]
            from backend.tools.menu_tools import get_menu_item_by_name
            item = await get_menu_item_by_name(item_name)
            if item:
                result = await remove_from_cart(call_id, item["id"])
                agent_response += f"Removed {item['name']} from your cart. " if result["success"] else f"Couldn't remove {item_name}. "
            else:
                agent_response += f"Couldn't find {item_name} in your cart. "

        elif name == "update_item_quantity":
            item_name = args["item_name"]
            qty = args["quantity"]
            from backend.tools.menu_tools import get_menu_item_by_name
            item = await get_menu_item_by_name(item_name)
            if item:
                result = await update_cart_quantity(call_id, item["id"], qty)
                agent_response += f"Updated {item['name']} quantity to {qty}. " if result["success"] else f"Couldn't update quantity. "

    if not agent_response:
        # Fallback: LLM text response
        agent_response = groq_service.extract_text(response_obj) or "How else can I help you?"

    # Refresh cart after modifications
    cart = await get_cart(call_id)
    return {**state, "current_cart": cart, "agent_response": agent_response.strip()}


# ─── Node: Billing ───────────────────────────────────────────────────────────

async def billing_node(state: AgentState) -> AgentState:
    """Calculate and voice-format the bill."""
    call_id = state["call_id"]
    delivery_info = state.get("delivery_info") or {}
    delivery_type = delivery_info.get("type", "delivery")

    bill = await get_bill_preview(call_id, delivery_type)
    if not bill.get("success"):
        response = "Your cart is empty. Please add items before checking the total."
    else:
        response = "Here's your bill: " + format_bill_for_voice(bill)
    return {**state, "billing_info": bill, "agent_response": response}


# ─── Node: Collect Customer Info ─────────────────────────────────────────────

async def collect_info_node(state: AgentState) -> AgentState:
    """
    Extract and store delivery information from the user's message.
    Uses the LLM to parse the address / name.
    """
    user_input = state.get("user_input", "")
    messages = [
        {
            "role": "system",
            "content": (
                "Extract delivery information from the customer's message. "
                "Return a JSON object with keys: type (delivery/pickup), "
                "address (string or null), name (string or null). "
                "Respond with ONLY valid JSON."
            ),
        },
        {"role": "user", "content": user_input},
    ]
    response = await groq_service.chat(messages=messages)
    raw = groq_service.extract_text(response).strip()
    try:
        info = json.loads(raw)
    except Exception:
        info = {}

    delivery_info = {**state.get("delivery_info", {}), **info}
    customer_name = info.get("name") or state.get("customer_name")

    # Acknowledge
    if delivery_info.get("address"):
        response_text = f"Got it. I'll deliver to {delivery_info['address']}."
    elif delivery_info.get("type") == "pickup":
        response_text = "Great, you'll be picking up your order."
    else:
        response_text = "Got it. Could you provide your delivery address?"

    return {
        **state,
        "delivery_info": delivery_info,
        "customer_name": customer_name,
        "agent_response": response_text,
    }


# ─── Node: Order Confirmation ────────────────────────────────────────────────

async def order_confirmation_node(state: AgentState) -> AgentState:
    """Confirm and place the order."""
    call_id = state["call_id"]
    intent = state.get("current_intent")

    if intent == "cancel_order":
        response = "No problem, I've cancelled your order. Is there anything else I can help you with?"
        return {**state, "agent_response": response, "order_state": "cancelled"}

    # Place order
    customer_name = state.get("customer_name") or "Guest"
    customer_phone = state["customer_phone"]
    delivery_info = state.get("delivery_info")
    session_id = state.get("session_id", call_id)

    result = await create_order_from_cart(
        call_id=call_id,
        conversation_id=session_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        delivery_info=delivery_info,
    )
    if result["success"]:
        order_id = result["order_id"]
        grand_total = result["grand_total"]
        response = (
            f"Your order has been placed successfully! "
            f"Order ID: {order_id[:8]}. Total: ₹{grand_total:.0f}. "
            f"Estimated delivery time: 30 to 45 minutes. "
            f"Thank you for ordering with us!"
        )
        return {
            **state,
            "order_id": order_id,
            "order_state": "confirmed",
            "agent_response": response,
        }
    else:
        response = f"Sorry, I couldn't place your order: {result.get('error')}. Please try again."
        return {**state, "agent_response": response}


# ─── Node: Order Status ──────────────────────────────────────────────────────

async def order_status_node(state: AgentState) -> AgentState:
    """Look up the customer's most recent order status."""
    phone = state["customer_phone"]
    orders = await get_orders_by_phone(phone, limit=1)
    if not orders:
        response = "I couldn't find any recent orders for your number."
    else:
        response = "Your latest order: " + format_order_for_voice(orders[0])
    return {**state, "agent_response": response}


# ─── Node: Generate Response ─────────────────────────────────────────────────

async def generate_response_node(state: AgentState) -> AgentState:
    """General-purpose LLM response generation with RAG context."""
    messages = [
        {"role": "system", "content": _build_system_prompt(state)},
    ]
    # Inject RAG context as a system message if available
    context = state.get("retrieved_context")
    if context:
        messages.append({
            "role": "system",
            "content": f"Relevant restaurant information:\n{context}",
        })

    messages.extend(state.get("messages", []))
    messages.append({"role": "user", "content": state.get("user_input", "")})

    response = await groq_service.chat(messages=messages)
    text = groq_service.extract_text(response)
    return {**state, "agent_response": text}


# ─── Node: End Call ──────────────────────────────────────────────────────────

async def end_call_node(state: AgentState) -> AgentState:
    """Graceful call termination with a goodbye message."""
    response = (
        "Thank you for calling! Your order is being prepared. "
        "Have a great day! Goodbye!"
    )
    return {**state, "agent_response": response, "should_end": True}

from __future__ import annotations

from langchain_core.messages import AIMessage

from app.agents.state import UIProjectState
from app.core.capability_response import build_capability_reply


async def direct_chat_node(state: UIProjectState) -> dict:
    """Handle chat-first capability/help questions without triggering page generation."""
    reply = build_capability_reply(state)
    return {
        "main_messages": [AIMessage(content=reply)],
        "intent_route": "direct_chat_node",
        "agent_backends": {
            "direct_chat_node": "deterministic_capability_reply",
        },
    }

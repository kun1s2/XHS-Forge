from __future__ import annotations

from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage

from app.core.truth_safety import build_tool_safety_result, dumps_tool_safety_result


@wrap_tool_call(name="TruthSafeToolMiddleware")
async def truth_safe_tool_middleware(request, handler):
    """把 create_agent 子流里的工具失败改写成结构化安全返回。"""
    try:
        return await handler(request)
    except Exception as exc:  # pragma: no cover - exercised via agent runtime
        tool_name = str(getattr(request, "tool_call", {}).get("name") or "unknown_tool")
        payload = build_tool_safety_result(
            tool_name=tool_name,
            reason="tool_unavailable",
            next_action="ask_user_for_facts",
            detail=str(exc),
        )
        return ToolMessage(
            content=dumps_tool_safety_result(payload),
            tool_call_id=str(getattr(request, "tool_call", {}).get("id") or tool_name),
            status="error",
            name=tool_name,
        )

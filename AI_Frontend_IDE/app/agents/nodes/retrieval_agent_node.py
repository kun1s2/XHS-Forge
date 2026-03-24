from __future__ import annotations

from typing import Any

from app.agents.nodes.research_agent import research_agent
from app.agents.state import UIProjectState
from app.agents.tools_registry import RESEARCH_TOOLS
from app.core.agent_runtime import create_controlled_agent
from app.core.config import settings
from app.core.llm_factory import create_llm
from app.core.prompt_engineering import build_prompt_snapshot
from app.core.request_semantics import latest_user_text_from_messages

_retrieval_runner = None


def _get_retrieval_runner():
    global _retrieval_runner
    if _retrieval_runner is None:
        _retrieval_runner = create_controlled_agent(
            model=create_llm(
                model=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
                temperature=0,
            ),
            tools=RESEARCH_TOOLS,
            name="retrieval_agent",
            prompt=(
                "你是数码购买决策工作台里的 Retrieval Agent。"
                "你的职责是先判断当前请求最应该补什么证据、是否需要搜图、是否需要联网，"
                "必要时调用检索工具，然后给总控 graph 返回一句极简的取证摘要。"
                "不要直接写页面，不要替用户下最终购买结论。"
            ),
        )
    return _retrieval_runner


def _extract_summary(messages: list[Any]) -> str:
    snippets: list[str] = []
    for msg in messages:
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            text = " ".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
        else:
            text = str(content or "").strip()
        if text:
            snippets.append(text)
    return snippets[-1] if snippets else ""


async def retrieval_agent_node(state: UIProjectState) -> dict[str, Any]:
    """Lightweight create_agent wrapper around deterministic retrieval orchestration."""
    user_query = latest_user_text_from_messages(state.get("main_messages") or [])
    selected_id = str(state.get("selected_element_id") or "").strip() or "global"
    prompt = (
        f"用户当前请求：{user_query}\n"
        f"当前选中目标：{selected_id}\n"
        "如果需要真实图片或外部事实，请优先调用合适的检索工具，然后总结本轮该补的证据类型。"
    )
    runner = _get_retrieval_runner()
    agent_result = await runner.ainvoke({"messages": [("user", prompt)]})
    agent_summary = _extract_summary(agent_result.get("messages") or [])

    payload = await research_agent(state)
    payload.setdefault("agent_backends", {})
    payload["agent_backends"]["retrieval_agent"] = runner.backend
    payload.setdefault("turn_trace", {})
    payload["turn_trace"]["retrieval_agent"] = {
        "tool_plan_summary": agent_summary or "已按结构化优先 -> 混合检索补证据的策略继续执行。",
    }
    payload.setdefault("node_prompts", {})
    payload["node_prompts"]["retrieval_agent"] = build_prompt_snapshot(
        "retrieval_agent",
        system_prompt="Digital Purchase Retrieval Agent",
        user_prompt=prompt,
        assistant_payload={"summary": agent_summary},
    )
    return payload

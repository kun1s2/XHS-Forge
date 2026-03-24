from __future__ import annotations

from typing import Any

from app.agents.nodes.note_editor_node import note_editor_node
from app.agents.state import UIProjectState
from app.agents.tools_registry import inspect_component_state, inspect_note_state
from app.core.agent_runtime import create_controlled_agent
from app.core.config import settings
from app.core.llm_factory import create_llm
from app.core.prompt_engineering import build_prompt_snapshot
from app.core.request_semantics import latest_user_text_from_messages

_composition_runner = None


def _get_composition_runner():
    global _composition_runner
    if _composition_runner is None:
        _composition_runner = create_controlled_agent(
            model=create_llm(
                model=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
                temperature=0,
            ),
            tools=[inspect_note_state, inspect_component_state],
            name="composition_agent",
            prompt=(
                "你是数码购买决策工作台里的 Composition Agent。"
                "你的职责是先检查当前档案结构和目标区块，再总结本轮编辑应优先改哪里。"
                "必要时可以调用检查工具，但不要直接生成最终页面。"
            ),
        )
    return _composition_runner


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


async def composition_agent_node(state: UIProjectState) -> dict[str, Any]:
    """Lightweight create_agent wrapper around deterministic composition/edit execution."""
    user_query = latest_user_text_from_messages(state.get("main_messages") or [])
    selected_id = str(state.get("selected_element_id") or "").strip() or "global"
    prompt = (
        f"用户当前请求：{user_query}\n"
        f"当前目标：{selected_id}\n"
        "请先判断这轮更像改标题、改结论、补图片区还是改对比结构，再给一个极简编辑摘要。"
    )
    runner = _get_composition_runner()
    agent_result = await runner.ainvoke({"messages": [("user", prompt)]})
    agent_summary = _extract_summary(agent_result.get("messages") or [])

    payload = await note_editor_node(state)
    payload.setdefault("agent_backends", {})
    payload["agent_backends"]["composition_agent"] = runner.backend
    payload.setdefault("turn_trace", {})
    payload["turn_trace"]["composition_agent"] = {
        "tool_plan_summary": agent_summary or "已按容器优先、结果可验证的编辑策略继续执行。",
    }
    payload.setdefault("node_prompts", {})
    payload["node_prompts"]["composition_agent"] = build_prompt_snapshot(
        "composition_agent",
        system_prompt="Digital Purchase Composition Agent",
        user_prompt=prompt,
        assistant_payload={"summary": agent_summary},
    )
    return payload

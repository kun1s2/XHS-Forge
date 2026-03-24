from __future__ import annotations

from typing import Any

from app.agents.services.composition_service import composition_service
from app.agents.tools_registry import inspect_component_state, inspect_note_state
from app.core.agent_runtime import create_controlled_agent
from app.core.config import settings
from app.core.llm_factory import create_llm
from app.core.prompt_engineering import build_prompt_snapshot, load_prompt_template, render_string_prompt
from app.core.request_semantics import latest_user_text_from_messages
from app.services.skill_registry import build_skill_context

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
            name="composition_worker",
            prompt=load_prompt_template("workers/composition_system.md"),
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


async def composition_worker_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Controlled composition worker that edits the decision note and validates visible changes."""
    user_query = latest_user_text_from_messages(state.get("main_messages") or [])
    selected_id = str(state.get("selected_element_id") or "").strip() or "global"
    knowledge_plan = (
        state.get("knowledge_plan")
        if isinstance(state.get("knowledge_plan"), dict)
        else ((state.get("retrieved_knowledge") or {}).get("knowledge_plan") if isinstance(state.get("retrieved_knowledge"), dict) else {})
    )
    skill_context = build_skill_context(
        role="composition_worker",
        intent_decision=state.get("intent_decision") if isinstance(state.get("intent_decision"), dict) else {},
        knowledge_plan=knowledge_plan if isinstance(knowledge_plan, dict) else {},
    )
    selected_skills = [str(item) for item in (skill_context.get("selected_skills") or []) if str(item).strip()]
    prompt = render_string_prompt(
        "workers/composition_user.md",
        user_query=user_query,
        selected_id=selected_id,
        selected_skills=", ".join(selected_skills) or "无",
        tool_plan=skill_context.get("tool_plan") or [],
        skill_documents=skill_context.get("skill_documents") or {},
    )
    runner = _get_composition_runner()
    agent_result = await runner.ainvoke({"messages": [("user", prompt)]})
    agent_summary = _extract_summary(agent_result.get("messages") or [])

    payload = await composition_service(state)
    payload.setdefault("agent_backends", {})
    payload["agent_backends"]["composition_worker"] = runner.backend
    payload["selected_skills"] = selected_skills
    changed_blocks = list((((payload.get("turn_trace") or {}).get("changed_blocks")) or []))
    has_asset_change = bool((payload.get("note_document") or {}).get("assets")) or bool(payload.get("image_assets"))
    payload.setdefault("skill_trace", {})
    payload["skill_trace"]["composition_worker"] = {
        "selected_skills": selected_skills,
        "skill_tool_plan": skill_context.get("tool_plan") or [],
        "skill_execution_result": "success" if (changed_blocks or has_asset_change) else "no_effect",
        "skill_fallback": [],
    }
    payload.setdefault("turn_trace", {})
    payload["turn_trace"]["composition_worker"] = {
        "tool_plan_summary": agent_summary or "已按容器优先、结果可验证的编辑策略继续执行。",
        "selected_skills": selected_skills,
        "skill_tool_plan": skill_context.get("tool_plan") or [],
        "skill_execution_result": "success" if (changed_blocks or has_asset_change) else "no_effect",
        "skill_fallback": [],
    }
    payload["turn_trace"]["agentic_runtime"] = {
        "current_stage": "composition",
        "current_agent": "composition_worker",
        "selected_skills": selected_skills,
        "failure_point": "" if (changed_blocks or has_asset_change) else "composition_no_effect",
    }
    payload.setdefault("node_prompts", {})
    payload["node_prompts"]["composition_worker"] = build_prompt_snapshot(
        "composition_worker",
        system_prompt="Digital Purchase Composition Worker",
        user_prompt=prompt,
        assistant_payload={"summary": agent_summary},
    )
    return payload

from __future__ import annotations

import asyncio
from typing import Any

from app.agents.services.research_service import research_service
from app.agents.tools_registry import network_search
from app.core.agent_runtime import create_controlled_agent
from app.core.config import settings
from app.core.llm_factory import create_llm
from app.core.prompt_engineering import build_prompt_snapshot, load_prompt_template, render_string_prompt
from app.core.request_semantics import latest_user_text_from_state
from app.services.skill_registry import build_skill_context

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
            tools=[network_search],
            name="retrieval_worker",
            prompt=load_prompt_template("workers/retrieval_system.md"),
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


async def _safe_runner_summary(runner, prompt: str) -> tuple[str, str]:
    try:
        agent_result = await asyncio.wait_for(
            runner.ainvoke({"messages": [("user", prompt)]}),
            timeout=18,
        )
        return _extract_summary(agent_result.get("messages") or []), ""
    except TimeoutError:
        return "", "retrieval_worker_agent_runner_timeout"
    except Exception as exc:
        return "", f"retrieval_worker_agent_runner_error:{type(exc).__name__}"


async def retrieval_worker_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Controlled retrieval worker that delegates live evidence gathering to the research service."""
    user_query = latest_user_text_from_state(state)
    if not user_query:
        user_query = str(state.get("intent_source_query") or "").strip()
    if not user_query:
        resume_directive = state.get("resume_directive") if isinstance(state.get("resume_directive"), dict) else {}
        user_query = str(resume_directive.get("resume_query") or "").strip()
    selected_id = str(state.get("selected_element_id") or "").strip() or "global"
    knowledge_plan = (
        state.get("knowledge_plan")
        if isinstance(state.get("knowledge_plan"), dict)
        else ((state.get("retrieved_knowledge") or {}).get("knowledge_plan") if isinstance(state.get("retrieved_knowledge"), dict) else {})
    )
    skill_context = build_skill_context(
        role="retrieval_worker",
        intent_decision=state.get("intent_decision") if isinstance(state.get("intent_decision"), dict) else {},
        knowledge_plan=knowledge_plan if isinstance(knowledge_plan, dict) else {},
    )
    selected_skills = [str(item) for item in (skill_context.get("selected_skills") or []) if str(item).strip()]
    prompt = render_string_prompt(
        "workers/retrieval_user.md",
        user_query=user_query,
        selected_id=selected_id,
        selected_skills=", ".join(selected_skills) or "无",
        skills_snapshot=skill_context.get("snapshot") or "无",
        tool_plan=skill_context.get("tool_plan") or [],
        skill_documents=skill_context.get("skill_documents") or {},
    )
    runner = _get_retrieval_runner()
    agent_summary, runner_failure = await _safe_runner_summary(runner, prompt)

    try:
        payload = await asyncio.wait_for(research_service(state), timeout=35)
    except TimeoutError:
        payload = {
            "knowledge_plan": knowledge_plan if isinstance(knowledge_plan, dict) else {},
            "retrieved_knowledge": state.get("retrieved_knowledge") if isinstance(state.get("retrieved_knowledge"), dict) else {},
            "last_worker_result": {
                "worker_name": "retrieval_worker",
                "status": "failed",
                "failure_reason": "retrieval_worker_research_timeout",
                "changed_blocks": [],
                "assets_delta": [],
                "candidate_kb_delta": [],
            },
        }
    payload.setdefault("agent_backends", {})
    payload["agent_backends"]["retrieval_worker"] = runner.backend
    payload["selected_skills"] = selected_skills
    payload.setdefault("skill_trace", {})
    payload["skill_trace"]["retrieval_worker"] = {
        "selected_skills": selected_skills,
        "skill_tool_plan": skill_context.get("tool_plan") or [],
        "skill_execution_result": "success" if (payload.get("retrieved_knowledge") or {}).get("retrieval_summary") else "no_effect",
        "skill_fallback": [],
    }
    payload.setdefault("turn_trace", {})
    payload["turn_trace"]["retrieval_worker"] = {
        "tool_plan_summary": agent_summary or "已按结构化优先 -> 混合检索补证据的策略继续执行。",
        "selected_skills": selected_skills,
        "skill_tool_plan": skill_context.get("tool_plan") or [],
        "skill_execution_result": "success" if (payload.get("retrieved_knowledge") or {}).get("retrieval_summary") else "no_effect",
        "skill_fallback": [runner_failure] if runner_failure else [],
    }
    payload["turn_trace"]["agentic_runtime"] = {
        "current_stage": "retrieval",
        "current_agent": "retrieval_worker",
        "selected_skills": selected_skills,
        "failure_point": runner_failure,
    }
    payload.setdefault("worker_prompts", {})
    payload["worker_prompts"]["retrieval_worker"] = build_prompt_snapshot(
        "retrieval_worker",
        system_prompt="Digital Purchase Retrieval Worker",
        user_prompt=prompt,
        assistant_payload={"summary": agent_summary},
    )
    return payload

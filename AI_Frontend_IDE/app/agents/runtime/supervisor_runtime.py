from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Literal, TypedDict

from langchain.agents.middleware import (
    after_agent,
    before_agent,
    before_model,
    dynamic_prompt,
    wrap_model_call,
    wrap_tool_call,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.store.base import BaseStore
from langgraph.types import Command

from app.agents.runtime.session_state import SupervisorSessionState
from app.agents.services.artifact_service import get_knowledge_version
from app.agents.services.artifact_quality_service import apply_artifact_quality_fixes
from app.agents.services.runtime_protocol_service import (
    build_checkpoint_resume_directive,
    build_worker_result,
    derive_followup_resume_directive,
    derive_phase_from_state,
    PHASE_CHECKPOINT,
    PHASE_COMPOSITION,
    PHASE_CRITIQUE,
    PHASE_RESUME,
    PHASE_RETRIEVAL,
    transition_phase,
)
from app.agents.services.revision_service import (
    build_revision_plan,
    build_revision_result,
    build_revision_status,
)
from app.agents.services.session_state_service import ensure_session_runtime_defaults
from app.agents.workers.composition_worker import composition_worker_payload
from app.agents.workers.critique_worker import critique_worker_payload
from app.agents.workers.intent_worker import intent_worker
from app.agents.workers.retrieval_worker import retrieval_worker_payload
from app.agents.runtime.state_helpers import merge_state_patch
from app.core.agent_runtime import create_controlled_agent
from app.core.config import settings
from app.core.llm_factory import create_llm
from app.core.note_document import build_note_document_from_state
from app.core.prompt_engineering import load_prompt_template, render_string_prompt
from app.services.conversational_checkpoints import (
    apply_asset_checkpoint_decision,
    apply_fact_gap_checkpoint_decision,
    apply_fact_conflict_checkpoint_decision,
    apply_knowledge_review_checkpoint_decision,
    apply_structure_checkpoint_decision,
    apply_truth_mode_checkpoint_decision,
    build_asset_checkpoint,
    build_fact_conflict_checkpoint,
    build_fact_gap_checkpoint,
    build_knowledge_review_checkpoint,
    build_structure_checkpoint,
    build_truth_mode_checkpoint,
)
from app.services.knowledge_hub import build_knowledge_plan
from app.services.skill_registry import build_skill_context


class SupervisorStructuredResponse(TypedDict):
    reply: str
    next_step: str
    turn_outcome: Literal["checkpoint", "updated_note", "analysis", "failed"]


def _normalize_structured_response(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        return value.model_dump()
    if isinstance(value, dict):
        return deepcopy(value)
    return {}


def _latest_user_text(state: dict[str, Any]) -> str:
    for key in ("user_messages", "main_messages", "messages"):
        messages = list(state.get(key) or [])
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                content = msg.content
                if isinstance(content, list):
                    text = "".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
                else:
                    text = str(content or "")
                if text.strip():
                    return text.strip()
    return ""


def _sanitize_persistent_messages(messages: list[BaseMessage] | None) -> list[BaseMessage]:
    sanitized: list[BaseMessage] = []
    for msg in list(messages or []):
        if isinstance(msg, HumanMessage):
            sanitized.append(msg)
            continue
        if isinstance(msg, SystemMessage):
            sanitized.append(msg)
            continue
        if isinstance(msg, AIMessage):
            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                continue
            sanitized.append(msg)
            continue
        if isinstance(msg, ToolMessage):
            continue
    return sanitized


def _sanitize_model_messages(messages: list[BaseMessage] | None) -> list[BaseMessage]:
    sanitized: list[BaseMessage] = []
    pending_tool_calls: set[str] = set()

    for msg in list(messages or []):
        if isinstance(msg, ToolMessage):
            tool_call_id = str(getattr(msg, "tool_call_id", "") or "")
            if tool_call_id and tool_call_id in pending_tool_calls:
                sanitized.append(msg)
                pending_tool_calls.discard(tool_call_id)
            continue

        if isinstance(msg, AIMessage):
            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                pending_tool_calls = {
                    str(call.get("id") or "")
                    for call in tool_calls
                    if isinstance(call, dict) and str(call.get("id") or "").strip()
                }
                sanitized.append(msg)
                continue
            pending_tool_calls.clear()
            sanitized.append(msg)
            continue

        pending_tool_calls.clear()
        sanitized.append(msg)

    return sanitized


def _ensure_note_document(state: dict[str, Any]) -> dict[str, Any]:
    existing = state.get("note_document")
    if isinstance(existing, dict) and existing:
        return existing
    return build_note_document_from_state(state)


def _with_resume_token(checkpoint: dict[str, Any], runtime: ToolRuntime) -> dict[str, Any]:
    payload = deepcopy(checkpoint or {})
    configurable = (runtime.config or {}).get("configurable") or {}
    thread_id = str(configurable.get("thread_id") or payload.get("thread_id") or "")
    checkpoint_id = str(payload.get("checkpoint_id") or payload.get("action_type") or "checkpoint")
    payload["checkpoint_type"] = str(payload.get("action_type") or payload.get("checkpoint_type") or checkpoint_id)
    payload["resume_token"] = f"{thread_id}:{checkpoint_id}:{runtime.tool_call_id or 'resume'}"
    return payload


def _tool_trace_entry(runtime: ToolRuntime, *, worker_name: str, status: str, failure_reason: str | None = None) -> dict[str, Any]:
    configurable = (runtime.config or {}).get("configurable") or {}
    return {
        "tool_name": worker_name,
        "worker_name": worker_name,
        "tool_call_id": runtime.tool_call_id,
        "thread_id": str(configurable.get("thread_id") or ""),
        "status": status,
        "failure_reason": str(failure_reason or "").strip(),
    }


def _command_from_update(
    *,
    runtime: ToolRuntime,
    worker_name: str,
    summary: str,
    update: dict[str, Any],
    status: str = "success",
    failure_reason: str | None = None,
) -> Command:
    tool_message = ToolMessage(
        content=summary,
        name=worker_name,
        tool_call_id=runtime.tool_call_id or worker_name,
    )
    next_update = deepcopy(update)
    next_update["messages"] = [tool_message]
    next_update.setdefault("agent_backends", {})
    next_update["agent_backends"][worker_name] = "supervisor_worker_tool"
    next_update["active_worker"] = worker_name
    next_update.setdefault("resume_directive", None)
    next_update["tool_trace"] = {
        "calls": {
            str(runtime.tool_call_id or worker_name): _tool_trace_entry(
                runtime,
                worker_name=worker_name,
                status=status,
                failure_reason=failure_reason,
            )
        }
    }
    return Command(update=next_update)


def _candidate_records_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    knowledge = state.get("retrieved_knowledge") if isinstance(state.get("retrieved_knowledge"), dict) else {}
    candidate_payload = (knowledge or {}).get("candidate_session_kb") if isinstance(knowledge, dict) else {}
    return [item for item in ((candidate_payload or {}).get("records") or []) if isinstance(item, dict)]


def _pick_business_checkpoint(state: dict[str, Any]) -> dict[str, Any] | None:
    for builder in (
        build_truth_mode_checkpoint,
        build_structure_checkpoint,
        build_knowledge_review_checkpoint,
        build_fact_conflict_checkpoint,
        build_fact_gap_checkpoint,
        build_asset_checkpoint,
    ):
        payload = builder(state)
        if isinstance(payload, dict) and payload:
            return payload
    return None


async def _run_retrieval_payload(state: dict[str, Any]) -> dict[str, Any]:
    return await retrieval_worker_payload(state)


@tool
async def retrieval_worker(
    focus: str = "",
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> Command:
    """检索数码购买决策所需的结构化知识、混合检索证据和候选事实。"""
    state = dict(runtime.state or {})
    try:
        payload = await _run_retrieval_payload(state)
    except Exception as exc:
        failure_reason = f"retrieval_worker_runtime_error:{type(exc).__name__}"
        update = {
            "current_phase": "retrieval",
            "turn_trace": {
                "retrieval_worker": {
                    "tool_plan_summary": "检索 worker 运行失败，已保留当前会话状态。",
                    "selected_skills": list(state.get("selected_skills") or []),
                    "skill_tool_plan": [],
                    "skill_execution_result": "failed",
                    "skill_fallback": [failure_reason],
                },
                "agentic_runtime": {
                    "current_stage": "retrieval",
                    "current_agent": "retrieval_worker",
                    "selected_skills": list(state.get("selected_skills") or []),
                    "failure_point": failure_reason,
                },
            },
            "last_worker_result": build_worker_result(
                worker_name="retrieval_worker",
                status="failed",
                phase_entered=PHASE_RETRIEVAL,
                phase_exited=PHASE_RETRIEVAL,
                failure_reason=failure_reason,
            ),
        }
        return _command_from_update(
            runtime=runtime,
            worker_name="retrieval_worker",
            summary="这轮检索失败了，我先保留当前状态，等下一步继续处理。",
            update=update,
            status="failed",
            failure_reason=failure_reason,
        )
    merged = merge_state_patch(state, payload)
    checkpoint = _pick_business_checkpoint(merged)
    candidate_records = _candidate_records_from_state(merged)
    update = deepcopy(payload)
    update["current_phase"] = PHASE_RETRIEVAL
    update["last_worker_result"] = build_worker_result(
        worker_name="retrieval_worker",
        status="success" if payload else "no_effect",
        phase_entered=PHASE_RETRIEVAL,
        phase_exited=PHASE_CHECKPOINT if checkpoint else PHASE_RETRIEVAL,
        candidate_kb_delta=candidate_records[:8],
    )
    if checkpoint:
        update["pending_checkpoint"] = _with_resume_token(checkpoint, runtime)
        update["current_phase"] = PHASE_CHECKPOINT
    else:
        followup_directive = derive_followup_resume_directive({**state, **update})
        if followup_directive:
            update["resume_directive"] = followup_directive
    summary = str(
        (((payload.get("retrieved_knowledge") or {}).get("retrieval_summary") or {}).get("strategy"))
        or "已完成结构化优先检索，并准备进入下一步。"
    )
    return _command_from_update(
        runtime=runtime,
        worker_name="retrieval_worker",
        summary=summary,
        update=update,
        status="success" if payload else "no_effect",
    )


@tool
async def composition_worker(
    focus: str = "",
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> Command:
    """根据已审知识与素材修改购买决策档案，并返回可验证的区块变化。"""
    state = dict(runtime.state or {})
    try:
        payload = await composition_worker_payload(state)
    except Exception as exc:
        failure_reason = f"composition_worker_runtime_error:{type(exc).__name__}"
        update = {
            "current_phase": "composition",
            "turn_trace": {
                "composition_worker": {
                    "tool_plan_summary": "成品编辑 worker 运行失败，已保留当前页面。",
                    "selected_skills": list(state.get("selected_skills") or []),
                    "skill_tool_plan": [],
                    "skill_execution_result": "failed",
                    "skill_fallback": [failure_reason],
                },
                "agentic_runtime": {
                    "current_stage": "composition",
                    "current_agent": "composition_worker",
                    "selected_skills": list(state.get("selected_skills") or []),
                    "failure_point": failure_reason,
                },
            },
            "last_worker_result": build_worker_result(
                worker_name="composition_worker",
                status="failed",
                phase_entered=PHASE_COMPOSITION,
                phase_exited=PHASE_COMPOSITION,
                failure_reason=failure_reason,
            ),
        }
        return _command_from_update(
            runtime=runtime,
            worker_name="composition_worker",
            summary="这轮页面修改失败了，我先保留当前版本。",
            update=update,
            status="failed",
            failure_reason=failure_reason,
        )
    changed_blocks = list((((payload.get("turn_trace") or {}).get("changed_blocks")) or []))
    note_document = payload.get("note_document") if isinstance(payload.get("note_document"), dict) else {}
    asset_delta = [item for item in ((note_document or {}).get("assets") or []) if isinstance(item, dict)]
    failure_reason = "" if (changed_blocks or asset_delta) else "composition_no_effect"
    update = deepcopy(payload)
    update["current_phase"] = PHASE_COMPOSITION
    update["last_worker_result"] = build_worker_result(
        worker_name="composition_worker",
        status="success" if (changed_blocks or asset_delta) else "failed",
        phase_entered=PHASE_COMPOSITION,
        phase_exited=PHASE_COMPOSITION,
        changed_blocks=changed_blocks,
        assets_delta=asset_delta[:6],
        failure_reason=failure_reason,
    )
    summary = "已完成当前页面修改。" if (changed_blocks or asset_delta) else "这轮没有产生可见修改。"
    return _command_from_update(
        runtime=runtime,
        worker_name="composition_worker",
        summary=summary,
        update=update,
        status="success" if (changed_blocks or asset_delta) else "failed",
        failure_reason=failure_reason,
    )


@tool
async def critique_worker(
    focus: str = "",
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> Command:
    """复盘当前购买决策档案，区分知识缺口和表达缺口，并给出下一步建议。"""
    state = dict(runtime.state or {})
    try:
        payload = await critique_worker_payload(state)
    except Exception as exc:
        failure_reason = f"critique_worker_runtime_error:{type(exc).__name__}"
        update = {
            "current_phase": "critique",
            "turn_trace": {
                "critique_worker": {
                    "selected_skills": list(state.get("selected_skills") or []),
                    "skill_tool_plan": [],
                    "skill_execution_result": "failed",
                    "skill_fallback": [failure_reason],
                },
                "agentic_runtime": {
                    "current_stage": "critique",
                    "current_agent": "critique_worker",
                    "selected_skills": list(state.get("selected_skills") or []),
                    "failure_point": failure_reason,
                },
            },
            "last_worker_result": build_worker_result(
                worker_name="critique_worker",
                status="failed",
                phase_entered=PHASE_CRITIQUE,
                phase_exited=PHASE_CRITIQUE,
                failure_reason=failure_reason,
            ),
        }
        return _command_from_update(
            runtime=runtime,
            worker_name="critique_worker",
            summary="这轮复盘失败了，但我保留了当前页面和知识状态。",
            update=update,
            status="failed",
            failure_reason=failure_reason,
        )
    feedback = payload.get("critique_feedback") if isinstance(payload.get("critique_feedback"), dict) else {}
    update = deepcopy(payload)
    update["current_phase"] = PHASE_CRITIQUE
    update["last_worker_result"] = build_worker_result(
        worker_name="critique_worker",
        status="success" if feedback else "no_effect",
        phase_entered=PHASE_CRITIQUE,
        phase_exited=PHASE_CRITIQUE,
        commit_eligible=False,
        checkpoint_eligible=False,
    )
    summary = str((feedback.get("suggestions") or ["已完成复盘。"])[0] if feedback else "已完成复盘。")
    return _command_from_update(
        runtime=runtime,
        worker_name="critique_worker",
        summary=summary,
        update=update,
        status="success" if feedback else "no_effect",
    )


def _note_outline(state: dict[str, Any]) -> str:
    note_document = _ensure_note_document(state)
    blocks = list((note_document.get("blocks") or []))
    block_outline = [f"{idx + 1}. {block.get('type') or 'Block'}" for idx, block in enumerate(blocks[:8]) if isinstance(block, dict)]
    return "\n".join(block_outline) if block_outline else "当前还没有正式成品区块。"


def _select_runtime_tools(state: dict[str, Any]) -> list[Any]:
    intent_decision = state.get("intent_decision") if isinstance(state.get("intent_decision"), dict) else {}
    operation_type = str(intent_decision.get("operation_type") or "").lower()
    task_type = str(intent_decision.get("task_type") or "").lower()
    needs_research = bool(intent_decision.get("needs_research"))
    needs_assets = bool(intent_decision.get("needs_assets"))
    selected_block = str(state.get("selected_element_id") or "").strip()
    pending_checkpoint = state.get("pending_checkpoint") if isinstance(state.get("pending_checkpoint"), dict) else {}
    resume_directive = state.get("resume_directive") if isinstance(state.get("resume_directive"), dict) else {}
    revision_status = state.get("revision_status") if isinstance(state.get("revision_status"), dict) else {}
    primary_recipe = revision_status.get("primary_recipe") if isinstance(revision_status.get("primary_recipe"), dict) else {}

    if pending_checkpoint:
        return []
    if resume_directive:
        preferred_worker = str(resume_directive.get("preferred_worker") or "").strip()
        if preferred_worker == "retrieval_worker":
            return [retrieval_worker, composition_worker, critique_worker]
        if preferred_worker == "composition_worker":
            return [composition_worker, critique_worker]
        if preferred_worker == "critique_worker":
            return [critique_worker]
    if task_type == "inspect":
        return [critique_worker]
    if task_type in {"review", "ingest"}:
        return [retrieval_worker]
    if operation_type == "asset_edit" or needs_assets:
        return [retrieval_worker, composition_worker]
    if selected_block or operation_type in {"text_edit", "layout_edit"}:
        return [composition_worker, critique_worker] if not needs_research else [composition_worker, retrieval_worker, critique_worker]
    if primary_recipe:
        recipe_scope = str(primary_recipe.get("scope") or "").lower()
        if recipe_scope in {"factual_issues", "completeness_issues"}:
            return [retrieval_worker, composition_worker, critique_worker]
    if task_type in {"create", "edit"}:
        return [retrieval_worker, composition_worker, critique_worker]
    return [retrieval_worker, composition_worker, critique_worker]


@before_agent(state_schema=SupervisorSessionState, name="SessionContextMiddleware")
def _session_context_middleware(state: SupervisorSessionState, runtime) -> dict[str, Any]:
    defaults = ensure_session_runtime_defaults(dict(state))
    sanitized_main_messages = _sanitize_persistent_messages(list(state.get("main_messages") or []))
    sanitized_runtime_messages = _sanitize_persistent_messages(list(state.get("messages") or []))
    if sanitized_runtime_messages:
        defaults["messages"] = sanitized_runtime_messages
    if sanitized_main_messages:
        defaults["main_messages"] = sanitized_main_messages
    elif sanitized_runtime_messages:
        human_messages = [msg for msg in sanitized_runtime_messages if isinstance(msg, HumanMessage)]
        ai_messages = [msg for msg in sanitized_runtime_messages if isinstance(msg, AIMessage)]
        defaults["main_messages"] = human_messages + ai_messages
    return defaults


@before_model(state_schema=SupervisorSessionState, name="SkillSelectionMiddleware")
async def _intent_and_skill_middleware(state: SupervisorSessionState, runtime) -> dict[str, Any]:
    if state.get("pending_checkpoint"):
        return {}
    query = _latest_user_text(state)
    updates: dict[str, Any] = {}
    if query and str(state.get("intent_source_query") or "") != query:
        intent_payload = await intent_worker(state)
        updates.update(intent_payload)
        updates["intent_source_query"] = query
        updates["intent_route"] = "supervisor_agent"
    merged = merge_state_patch(dict(state), updates) if updates else dict(state)
    if query and str(merged.get("knowledge_plan_query") or "") != query:
        knowledge_plan = build_knowledge_plan(merged)  # type: ignore[arg-type]
        updates["knowledge_plan"] = knowledge_plan
        updates["knowledge_plan_query"] = query
    selected_bundle = build_skill_context(
        role="supervisor_agent",
        intent_decision=updates.get("intent_decision") if isinstance(updates.get("intent_decision"), dict) else state.get("intent_decision"),
        knowledge_plan=updates.get("knowledge_plan") if isinstance(updates.get("knowledge_plan"), dict) else state.get("knowledge_plan"),
    )
    selected_skills = [str(item) for item in (selected_bundle.get("selected_skills") or []) if str(item).strip()]
    updates["selected_skills"] = selected_skills
    updates.setdefault("skill_trace", {})
    updates["skill_trace"]["supervisor"] = {
        "selected_skills": selected_skills,
        "skill_tool_plan": selected_bundle.get("tool_plan") or [],
        "skill_execution_result": "prepared",
        "skill_fallback": [],
    }
    return updates


@before_model(state_schema=SupervisorSessionState, name="CheckpointMiddleware")
def _checkpoint_middleware(state: SupervisorSessionState, runtime) -> dict[str, Any]:
    checkpoint = state.get("pending_checkpoint")
    if isinstance(checkpoint, dict) and checkpoint:
        return {"current_phase": PHASE_CHECKPOINT, "active_worker": "checkpoint"}
    return {}


@before_model(state_schema=SupervisorSessionState, name="SessionPhaseMiddleware")
def _phase_middleware(state: SupervisorSessionState, runtime) -> dict[str, Any]:
    current_phase = derive_phase_from_state(dict(state))
    return {
        "current_phase": transition_phase(state.get("current_phase"), current_phase),
        "active_worker": "checkpoint" if current_phase == PHASE_CHECKPOINT else str(state.get("active_worker") or "supervisor"),
    }


@dynamic_prompt
def _supervisor_dynamic_prompt(request) -> str:
    state = dict(request.state or {})
    note_outline = _note_outline(state)
    knowledge_plan = state.get("knowledge_plan") if isinstance(state.get("knowledge_plan"), dict) else {}
    pending_checkpoint = state.get("pending_checkpoint") if isinstance(state.get("pending_checkpoint"), dict) else {}
    resume_directive = state.get("resume_directive") if isinstance(state.get("resume_directive"), dict) else {}
    last_worker_result = state.get("last_worker_result") if isinstance(state.get("last_worker_result"), dict) else {}
    intent_decision = state.get("intent_decision") if isinstance(state.get("intent_decision"), dict) else {}
    selected_skills = [str(item) for item in (state.get("selected_skills") or []) if str(item).strip()]
    return render_string_prompt(
        "runtime/supervisor_dynamic.md",
        intent_decision=json.dumps(intent_decision, ensure_ascii=False),
        knowledge_plan=json.dumps(knowledge_plan, ensure_ascii=False),
        selected_skills=json.dumps(selected_skills, ensure_ascii=False),
        pending_checkpoint=json.dumps(pending_checkpoint, ensure_ascii=False),
        resume_directive=json.dumps(resume_directive, ensure_ascii=False),
        last_worker_result=json.dumps(last_worker_result, ensure_ascii=False),
        note_outline=note_outline,
    )


@wrap_model_call(name="DynamicToolSelectionMiddleware")
async def _dynamic_tool_selection_middleware(request, handler):
    allowed_tools = _select_runtime_tools(dict(request.state or {}))
    clean_messages = _sanitize_model_messages(list(request.messages or []))
    sanitized_state = dict(request.state or {})
    sanitized_state["messages"] = clean_messages
    return await handler(request.override(tools=allowed_tools, messages=clean_messages, state=sanitized_state))


@wrap_tool_call(name="ToolGuardMiddleware")
async def _tool_guard_middleware(request, handler):
    allowed = {
        "retrieval_worker",
        "composition_worker",
        "critique_worker",
    }
    if request.tool is None or request.tool.name not in allowed:
        return ToolMessage(
            content=f"工具 {getattr(request.tool, 'name', 'unknown')} 不在正式 supervisor worker 白名单内。",
            name=getattr(request.tool, "name", "unknown"),
            tool_call_id=request.tool_call.get("id", "tool_guard"),
            status="error",
        )
    return await handler(request)


@after_agent(state_schema=SupervisorSessionState, name="ResultValidationMiddleware")
def _result_validation_middleware(state: SupervisorSessionState, runtime) -> dict[str, Any]:
    note_document = _ensure_note_document(state)
    turn_trace = deepcopy(state.get("turn_trace") or {})
    agentic_runtime = deepcopy(turn_trace.get("agentic_runtime") or {})
    last_worker_result = state.get("last_worker_result") if isinstance(state.get("last_worker_result"), dict) else {}
    quality_patch = apply_artifact_quality_fixes({**dict(state), "note_document": note_document})
    note_document = quality_patch.get("note_document") if isinstance(quality_patch.get("note_document"), dict) else note_document
    artifact_quality = quality_patch.get("artifact_quality") if isinstance(quality_patch.get("artifact_quality"), dict) else {}
    autofix_changed_blocks = [
        item for item in (quality_patch.get("autofix_changed_blocks") or [])
        if isinstance(item, dict)
    ]
    if autofix_changed_blocks:
        existing_changed = [
            item for item in ((turn_trace.get("changed_blocks") or []))
            if isinstance(item, dict)
        ]
        seen_pairs = {
            (str(item.get("id") or "").strip(), str(item.get("type") or "").strip())
            for item in existing_changed
        }
        for item in autofix_changed_blocks:
            pair = (str(item.get("id") or "").strip(), str(item.get("type") or "").strip())
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            existing_changed.append(deepcopy(item))
        turn_trace["changed_blocks"] = existing_changed
    next_last_worker_result = deepcopy(last_worker_result)
    if artifact_quality and not bool(artifact_quality.get("passed")) and next_last_worker_result:
        if str(next_last_worker_result.get("worker_name") or "").strip() == "composition_worker":
            next_last_worker_result["status"] = "failed"
            next_last_worker_result["failure_reason"] = str(artifact_quality.get("failure_reason") or "artifact_quality_failed").strip()
            next_last_worker_result["commit_eligible"] = False
    enriched_state = {
        **dict(state),
        "note_document": note_document,
        "turn_trace": turn_trace,
        "artifact_quality": artifact_quality,
        "last_worker_result": next_last_worker_result or last_worker_result,
    }
    revision_plan = build_revision_plan(enriched_state)
    revision_result = build_revision_result({**enriched_state, "revision_plan": revision_plan})
    revision_status = build_revision_status(
        {
            **enriched_state,
            "revision_plan": revision_plan,
            "revision_result": revision_result,
        }
    )
    failure_reason = str((next_last_worker_result or last_worker_result).get("failure_reason") or "").strip()
    agentic_runtime.update(
        {
            "current_stage": str(state.get("current_phase") or "supervisor"),
            "current_agent": str(state.get("active_worker") or "supervisor"),
            "selected_skills": list(state.get("selected_skills") or []),
            "failure_point": failure_reason,
            "knowledge_version": get_knowledge_version(dict(state)),
        }
    )
    turn_trace["agentic_runtime"] = agentic_runtime
    turn_trace["revision"] = {
        "status": revision_status.get("status"),
        "reason": revision_plan.get("reason"),
        "scope": revision_plan.get("scope"),
        "target_block_id": revision_plan.get("target_block_id"),
        "changed_blocks": revision_result.get("changed_blocks") or [],
        "failure_reason": revision_result.get("failure_reason") or "",
    }
    turn_trace["artifact_quality"] = deepcopy(artifact_quality)
    pending_checkpoint = state.get("pending_checkpoint") if isinstance(state.get("pending_checkpoint"), dict) else {}
    if pending_checkpoint:
        turn_trace.setdefault("conversation_checkpoints", {})
        turn_trace["conversation_checkpoints"]["pending"] = {
            "type": str(pending_checkpoint.get("checkpoint_type") or pending_checkpoint.get("action_type") or ""),
            "checkpoint_id": str(pending_checkpoint.get("checkpoint_id") or ""),
            "title": str(pending_checkpoint.get("title") or ""),
        }
    resume_directive = state.get("resume_directive") if isinstance(state.get("resume_directive"), dict) else {}
    if resume_directive:
        turn_trace["resume_directive"] = deepcopy(resume_directive)
    else:
        followup_directive = derive_followup_resume_directive(dict(state))
        if followup_directive:
            resume_directive = followup_directive
            turn_trace["resume_directive"] = deepcopy(followup_directive)
    normalized_structured_response = _normalize_structured_response(state.get("structured_response"))
    update = {
        "note_document": note_document,
        "turn_trace": turn_trace,
        "artifact_quality": artifact_quality,
        "revision_plan": revision_plan,
        "revision_result": revision_result,
        "revision_status": revision_status,
        "last_worker_result": next_last_worker_result or last_worker_result,
        **({"structured_response": normalized_structured_response} if normalized_structured_response else {}),
    }
    if resume_directive:
        update["resume_directive"] = resume_directive
    return update


@after_agent(state_schema=SupervisorSessionState, name="TelemetryMiddleware")
def _telemetry_middleware(state: SupervisorSessionState, runtime) -> dict[str, Any]:
    structured_response = _normalize_structured_response(state.get("structured_response"))
    if not structured_response:
        return {}
    return {
        "turn_trace": {
            "supervisor_decision": structured_response,
        }
    }


def apply_supervisor_checkpoint_decision(state: dict[str, Any], decision_payload: dict[str, Any]) -> dict[str, Any]:
    pending = state.get("pending_checkpoint") if isinstance(state.get("pending_checkpoint"), dict) else {}
    checkpoint_type = str(
        decision_payload.get("action_type")
        or pending.get("checkpoint_type")
        or pending.get("action_type")
        or ""
    ).strip()
    handlers = {
        "truth_mode_checkpoint": apply_truth_mode_checkpoint_decision,
        "structure_checkpoint": apply_structure_checkpoint_decision,
        "knowledge_review_checkpoint": apply_knowledge_review_checkpoint_decision,
        "asset_checkpoint": apply_asset_checkpoint_decision,
        "fact_gap_checkpoint": apply_fact_gap_checkpoint_decision,
        "fact_conflict_checkpoint": apply_fact_conflict_checkpoint_decision,
    }
    if checkpoint_type in handlers:
        patch = handlers[checkpoint_type](state, decision_payload)  # type: ignore[arg-type]
    else:
        patch = {
            "checkpoint_decision": deepcopy(decision_payload),
        }
    patch["pending_checkpoint"] = None
    patch["resume_directive"] = build_checkpoint_resume_directive(
        state=state,
        checkpoint_type=checkpoint_type,
        decision_payload=decision_payload,
    )
    patch["current_phase"] = PHASE_RESUME
    patch["active_worker"] = str(
        ((patch.get("resume_directive") if isinstance(patch.get("resume_directive"), dict) else {}) or {}).get("preferred_worker")
        or "supervisor"
    )
    patch.setdefault("checkpoint_decision", {})
    patch["checkpoint_decision"]["last"] = deepcopy(decision_payload)
    return patch


def build_supervisor_runtime(checkpointer, store: BaseStore | None = None):
    tools = [
        retrieval_worker,
        composition_worker,
        critique_worker,
    ]
    middleware = [
        _session_context_middleware,
        _intent_and_skill_middleware,
        _checkpoint_middleware,
        _phase_middleware,
        _dynamic_tool_selection_middleware,
        _tool_guard_middleware,
        _result_validation_middleware,
        _telemetry_middleware,
        _supervisor_dynamic_prompt,
    ]
    return create_controlled_agent(
        model=create_llm(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            temperature=0,
            max_retries=2,
        ),
        tools=tools,
        prompt=load_prompt_template("runtime/supervisor_system.md"),
        state_schema=SupervisorSessionState,
        checkpointer=checkpointer,
        store=store,
        middleware=middleware,
        response_format=SupervisorStructuredResponse,
        name="supervisor_agent",
    )

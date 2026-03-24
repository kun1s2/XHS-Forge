from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Literal

from langchain.agents.middleware import (
    after_agent,
    before_agent,
    before_model,
    dynamic_prompt,
    wrap_tool_call,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.store.base import BaseStore
from langgraph.types import Command

from app.agents.runtime.session_state import SupervisorSessionState
from app.agents.services.artifact_service import get_knowledge_version
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
from app.agents.state import merge_state_patch
from app.core.agent_runtime import create_controlled_agent
from app.core.config import settings
from app.core.llm_factory import create_llm
from app.core.note_document import build_note_document_from_state
from app.core.prompt_engineering import load_prompt_template, render_string_prompt
from app.services.conversational_checkpoints import (
    apply_asset_checkpoint_decision,
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


class SupervisorStructuredResponse(BaseModel):
    reply: str = Field(..., description="用户这轮能直接看到的自然语言回复")
    next_step: str = Field(..., description="本轮结束后最建议继续推进的下一步")
    turn_outcome: Literal["checkpoint", "updated_note", "analysis", "failed"] = Field(
        ...,
        description="本轮运行结果类型",
    )


def _latest_user_text(state: dict[str, Any]) -> str:
    messages = list(state.get("main_messages") or state.get("messages") or [])
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


def _make_worker_result(
    *,
    worker_name: str,
    status: str,
    changed_blocks: list[dict[str, Any]] | None = None,
    assets_delta: list[dict[str, Any]] | None = None,
    candidate_kb_delta: list[dict[str, Any]] | None = None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "worker_name": worker_name,
        "status": status,
        "changed_blocks": list(changed_blocks or []),
        "assets_delta": list(assets_delta or []),
        "candidate_kb_delta": list(candidate_kb_delta or []),
        "failure_reason": str(failure_reason or "").strip(),
    }


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
    payload = await _run_retrieval_payload(state)
    merged = merge_state_patch(state, payload)
    checkpoint = _pick_business_checkpoint(merged)
    candidate_records = _candidate_records_from_state(merged)
    update = deepcopy(payload)
    update["current_phase"] = "retrieval"
    update["last_worker_result"] = _make_worker_result(
        worker_name="retrieval_worker",
        status="success" if payload else "no_effect",
        candidate_kb_delta=candidate_records[:8],
    )
    if checkpoint:
        update["pending_checkpoint"] = _with_resume_token(checkpoint, runtime)
        update["current_phase"] = "knowledge_review"
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
async def review_worker(
    focus: str = "",
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> Command:
    """整理候选知识、冲突事实和待审项，并在需要时发起业务级 checkpoint。"""
    state = dict(runtime.state or {})
    checkpoint = _pick_business_checkpoint(state)
    status = "success" if checkpoint else "no_effect"
    update: dict[str, Any] = {
        "current_phase": "knowledge_review",
        "last_worker_result": _make_worker_result(worker_name="review_worker", status=status),
    }
    if checkpoint:
        update["pending_checkpoint"] = _with_resume_token(checkpoint, runtime)
        summary = str(checkpoint.get("summary") or checkpoint.get("title") or "需要你确认一项关键信息。")
    else:
        summary = "当前没有新的待审知识或冲突事实。"
    return _command_from_update(
        runtime=runtime,
        worker_name="review_worker",
        summary=summary,
        update=update,
        status=status,
    )


@tool
async def asset_worker(
    focus: str = "",
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> Command:
    """判断当前档案是否缺图，必要时补搜图片并生成素材使用 checkpoint。"""
    state = dict(runtime.state or {})
    intent = deepcopy(state.get("intent_decision") if isinstance(state.get("intent_decision"), dict) else {})
    intent.update(
        {
            "task_type": "edit",
            "operation_type": "asset_edit",
            "scope": str(intent.get("scope") or "global_canvas"),
            "needs_research": True,
            "needs_assets": True,
            "confidence": float(intent.get("confidence") or 0.99),
            "fallback_required": False,
        }
    )
    asset_state = merge_state_patch(state, {"intent_decision": intent})
    payload = await _run_retrieval_payload(asset_state)
    merged = merge_state_patch(asset_state, payload)
    checkpoint = build_asset_checkpoint(merged)
    image_assets = [item for item in (merged.get("image_assets") or []) if isinstance(item, dict) and str(item.get("url") or "").strip()]
    update = deepcopy(payload)
    update["current_phase"] = "asset"
    update["last_worker_result"] = _make_worker_result(
        worker_name="asset_worker",
        status="success" if image_assets else "failed",
        assets_delta=image_assets[:6],
        failure_reason="" if image_assets else "asset_search_no_result",
    )
    if checkpoint:
        update["pending_checkpoint"] = _with_resume_token(checkpoint, runtime)
    summary = "已补充图片候选，等待你确认素材使用方式。" if checkpoint else ("已补充图片素材。" if image_assets else "这轮还没补图成功。")
    return _command_from_update(
        runtime=runtime,
        worker_name="asset_worker",
        summary=summary,
        update=update,
        status="success" if image_assets else "failed",
        failure_reason="" if image_assets else "asset_search_no_result",
    )


@tool
async def composition_worker(
    focus: str = "",
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> Command:
    """根据已审知识与素材修改购买决策档案，并返回可验证的区块变化。"""
    state = dict(runtime.state or {})
    payload = await composition_worker_payload(state)
    changed_blocks = list((((payload.get("turn_trace") or {}).get("changed_blocks")) or []))
    note_document = payload.get("note_document") if isinstance(payload.get("note_document"), dict) else {}
    asset_delta = [item for item in ((note_document or {}).get("assets") or []) if isinstance(item, dict)]
    failure_reason = "" if (changed_blocks or asset_delta) else "composition_no_effect"
    update = deepcopy(payload)
    update["current_phase"] = "composition"
    update["last_worker_result"] = _make_worker_result(
        worker_name="composition_worker",
        status="success" if (changed_blocks or asset_delta) else "failed",
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
    payload = await critique_worker_payload(state)
    feedback = payload.get("critique_feedback") if isinstance(payload.get("critique_feedback"), dict) else {}
    update = deepcopy(payload)
    update["current_phase"] = "critique"
    update["last_worker_result"] = _make_worker_result(
        worker_name="critique_worker",
        status="success" if feedback else "no_effect",
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


@before_agent(state_schema=SupervisorSessionState, name="SessionContextMiddleware")
def _session_context_middleware(state: SupervisorSessionState, runtime) -> dict[str, Any]:
    defaults = ensure_session_runtime_defaults(dict(state))
    if state.get("main_messages") is None and state.get("messages"):
        human_messages = [msg for msg in (state.get("messages") or []) if isinstance(msg, HumanMessage)]
        if human_messages:
            defaults["main_messages"] = human_messages
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


@before_model(state_schema=SupervisorSessionState, can_jump_to=["end"], name="CheckpointMiddleware")
def _checkpoint_middleware(state: SupervisorSessionState, runtime) -> Command[Any] | None:
    checkpoint = state.get("pending_checkpoint")
    if isinstance(checkpoint, dict) and checkpoint:
        return Command(update={"current_phase": "checkpoint", "active_worker": "checkpoint"}, goto="end")
    return None


@before_model(state_schema=SupervisorSessionState, name="SessionPhaseMiddleware")
def _phase_middleware(state: SupervisorSessionState, runtime) -> dict[str, Any]:
    return {
        "current_phase": str(state.get("current_phase") or "supervisor"),
        "active_worker": str(state.get("active_worker") or "supervisor"),
    }


@dynamic_prompt
def _supervisor_dynamic_prompt(request) -> str:
    state = dict(request.state or {})
    note_outline = _note_outline(state)
    knowledge_plan = state.get("knowledge_plan") if isinstance(state.get("knowledge_plan"), dict) else {}
    pending_checkpoint = state.get("pending_checkpoint") if isinstance(state.get("pending_checkpoint"), dict) else {}
    last_worker_result = state.get("last_worker_result") if isinstance(state.get("last_worker_result"), dict) else {}
    intent_decision = state.get("intent_decision") if isinstance(state.get("intent_decision"), dict) else {}
    selected_skills = [str(item) for item in (state.get("selected_skills") or []) if str(item).strip()]
    return render_string_prompt(
        "runtime/supervisor_dynamic.md",
        intent_decision=json.dumps(intent_decision, ensure_ascii=False),
        knowledge_plan=json.dumps(knowledge_plan, ensure_ascii=False),
        selected_skills=json.dumps(selected_skills, ensure_ascii=False),
        pending_checkpoint=json.dumps(pending_checkpoint, ensure_ascii=False),
        last_worker_result=json.dumps(last_worker_result, ensure_ascii=False),
        note_outline=note_outline,
    )


@wrap_tool_call(name="ToolGuardMiddleware")
async def _tool_guard_middleware(request, handler):
    allowed = {
        "retrieval_worker",
        "review_worker",
        "asset_worker",
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
    revision_plan = build_revision_plan(dict(state))
    revision_result = build_revision_result({**dict(state), "revision_plan": revision_plan})
    revision_status = build_revision_status(
        {
            **dict(state),
            "revision_plan": revision_plan,
            "revision_result": revision_result,
        }
    )
    failure_reason = str(last_worker_result.get("failure_reason") or "").strip()
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
    pending_checkpoint = state.get("pending_checkpoint") if isinstance(state.get("pending_checkpoint"), dict) else {}
    if pending_checkpoint:
        turn_trace.setdefault("conversation_checkpoints", {})
        turn_trace["conversation_checkpoints"]["pending"] = {
            "type": str(pending_checkpoint.get("checkpoint_type") or pending_checkpoint.get("action_type") or ""),
            "checkpoint_id": str(pending_checkpoint.get("checkpoint_id") or ""),
            "title": str(pending_checkpoint.get("title") or ""),
        }
    return {
        "note_document": note_document,
        "turn_trace": turn_trace,
        "revision_plan": revision_plan,
        "revision_result": revision_result,
        "revision_status": revision_status,
    }


@after_agent(state_schema=SupervisorSessionState, name="TelemetryMiddleware")
def _telemetry_middleware(state: SupervisorSessionState, runtime) -> dict[str, Any]:
    structured_response = state.get("structured_response")
    if not isinstance(structured_response, dict):
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
        "fact_conflict_checkpoint": apply_fact_conflict_checkpoint_decision,
    }
    if checkpoint_type in handlers:
        patch = handlers[checkpoint_type](state, decision_payload)  # type: ignore[arg-type]
    elif checkpoint_type == "fact_gap_checkpoint":
        patch = {
            "user_provided_facts": deepcopy(decision_payload.get("user_provided_facts") or {}),
            "checkpoint_progress": {
                "fact_gap": {
                    "resolved": True,
                    "selected": str(decision_payload.get("decision") or ""),
                }
            },
        }
    else:
        patch = {
            "checkpoint_decision": deepcopy(decision_payload),
        }
    patch["pending_checkpoint"] = {}
    patch.setdefault("checkpoint_decision", {})
    patch["checkpoint_decision"]["last"] = deepcopy(decision_payload)
    return patch


def build_supervisor_runtime(checkpointer, store: BaseStore | None = None):
    tools = [
        retrieval_worker,
        review_worker,
        asset_worker,
        composition_worker,
        critique_worker,
    ]
    middleware = [
        _session_context_middleware,
        _intent_and_skill_middleware,
        _checkpoint_middleware,
        _phase_middleware,
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

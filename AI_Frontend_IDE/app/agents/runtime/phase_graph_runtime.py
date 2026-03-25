from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.store.base import BaseStore

from app.agents.runtime.session_state import SupervisorSessionState
from app.agents.runtime.state_helpers import merge_state_patch
from app.agents.services.artifact_quality_service import apply_artifact_quality_fixes
from app.agents.services.artifact_service import build_artifact_patch, ensure_artifact_manifest, get_knowledge_version
from app.agents.services.revision_service import (
    build_revision_plan,
    build_revision_result,
    build_revision_status,
    reconcile_revision_result,
)
from app.agents.services.runtime_protocol_service import (
    PHASE_CHECKPOINT,
    PHASE_COMMIT,
    PHASE_COMPOSITION,
    PHASE_CRITIQUE,
    PHASE_DONE,
    PHASE_FAILED,
    PHASE_INTENT,
    PHASE_RESUME,
    PHASE_RETRIEVAL,
    build_worker_result,
    derive_followup_resume_directive,
    should_commit_artifact_version,
    transition_phase,
)
from app.agents.services.session_state_service import ensure_session_runtime_defaults
from app.agents.utils.entity_utils import resolve_state_entity_name
from app.agents.workers.composition_worker import composition_worker_payload
from app.agents.workers.critique_worker import critique_worker_payload
from app.agents.workers.intent_worker import intent_worker
from app.agents.workers.retrieval_worker import retrieval_worker_payload
from app.core.note_document import build_note_document_from_state
from app.services.conversational_checkpoints import (
    build_asset_checkpoint,
    build_fact_conflict_checkpoint,
    build_fact_gap_checkpoint,
    build_knowledge_review_checkpoint,
    build_structure_checkpoint,
    build_truth_mode_checkpoint,
)
from app.services.knowledge_hub import build_knowledge_plan
from app.services.skill_registry import build_skill_context


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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
                text = text.strip()
                if text:
                    return text
    return ""


def _sanitize_persistent_messages(messages: list[BaseMessage] | None) -> list[BaseMessage]:
    sanitized: list[BaseMessage] = []
    for msg in list(messages or []):
        if isinstance(msg, (HumanMessage, SystemMessage)):
            sanitized.append(msg)
            continue
        if isinstance(msg, AIMessage):
            if getattr(msg, "tool_calls", None):
                continue
            sanitized.append(msg)
            continue
        if isinstance(msg, ToolMessage):
            continue
    return sanitized


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


def _tool_trace(worker_name: str, *, status: str, failure_reason: str = "") -> dict[str, Any]:
    return {
        "calls": {
            worker_name: {
                "tool_name": worker_name,
                "worker_name": worker_name,
                "status": status,
                "failure_reason": failure_reason,
            }
        }
    }


def _note_outline(state: dict[str, Any]) -> str:
    note_document = state.get("note_document") if isinstance(state.get("note_document"), dict) else build_note_document_from_state(state)
    blocks = list((note_document.get("blocks") or []))
    block_outline = [f"{idx + 1}. {block.get('type') or 'Block'}" for idx, block in enumerate(blocks[:8]) if isinstance(block, dict)]
    return "\n".join(block_outline) if block_outline else "当前还没有正式成品区块。"


def _merge_changed_blocks(existing: list[dict[str, Any]], additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = [deepcopy(item) for item in existing if isinstance(item, dict)]
    seen = {(str(item.get("id") or "").strip(), str(item.get("type") or "").strip()) for item in merged}
    for item in additions:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("id") or "").strip(), str(item.get("type") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        merged.append(deepcopy(item))
    return merged


async def _run_intent_node(state: SupervisorSessionState) -> dict[str, Any]:
    base = ensure_session_runtime_defaults(dict(state))
    update: dict[str, Any] = {}
    sanitized_main_messages = _sanitize_persistent_messages(list(base.get("main_messages") or []))
    sanitized_messages = _sanitize_persistent_messages(list(base.get("messages") or []))
    sanitized_user_messages = [
        msg for msg in _sanitize_persistent_messages(list(base.get("user_messages") or []))
        if isinstance(msg, HumanMessage)
    ]
    if sanitized_main_messages:
        update["main_messages"] = sanitized_main_messages
    if sanitized_messages:
        update["messages"] = sanitized_messages
    if sanitized_user_messages:
        update["user_messages"] = sanitized_user_messages

    query = _latest_user_text({**base, **update})
    merged = merge_state_patch(base, update) if update else dict(base)
    if query and str(merged.get("intent_source_query") or "") != query:
        intent_patch = await intent_worker(merged)
        update = merge_state_patch(update, intent_patch)
        update["intent_source_query"] = query
    merged = merge_state_patch(base, update) if update else dict(base)
    if query and str(merged.get("knowledge_plan_query") or "") != query:
        update["knowledge_plan"] = build_knowledge_plan(merged)  # type: ignore[arg-type]
        update["knowledge_plan_query"] = query

    merged = merge_state_patch(base, update) if update else dict(base)
    selected_bundle = build_skill_context(
        role="supervisor_agent",
        intent_decision=merged.get("intent_decision") if isinstance(merged.get("intent_decision"), dict) else {},
        knowledge_plan=merged.get("knowledge_plan") if isinstance(merged.get("knowledge_plan"), dict) else {},
    )
    selected_skills = [str(item) for item in (selected_bundle.get("selected_skills") or []) if str(item).strip()]
    update["selected_skills"] = selected_skills
    update.setdefault("skill_trace", {})
    update["skill_trace"]["supervisor_agent"] = {
        "selected_skills": selected_skills,
        "skill_tool_plan": selected_bundle.get("tool_plan") or [],
        "skill_execution_result": "prepared",
        "skill_fallback": [],
    }
    entity_anchor = resolve_state_entity_name(merge_state_patch(base, update), query)
    if entity_anchor:
        update["entity_anchor"] = entity_anchor
        update["artifact_target"] = entity_anchor
    update["artifact"] = ensure_artifact_manifest(merge_state_patch(base, update))
    update["current_phase"] = transition_phase(base.get("current_phase"), PHASE_INTENT)
    update["active_worker"] = "supervisor_agent"
    return update


def _route_from_supervisor(state: SupervisorSessionState) -> str:
    if _as_dict(state.get("pending_checkpoint")):
        return "checkpoint"
    if _as_dict(state.get("resume_directive")):
        return "resume"

    last_worker_result = _as_dict(state.get("last_worker_result"))
    if str(last_worker_result.get("status") or "").strip() == "failed":
        return "failed"

    intent_route = str(state.get("intent_route") or "").strip()
    if intent_route == "composition_worker":
        return "composition_worker"
    if intent_route == "critique_worker":
        return "critique_worker"
    return "retrieval_worker"


async def _run_retrieval_node(state: SupervisorSessionState, config: RunnableConfig | None = None) -> dict[str, Any]:
    current = dict(state)
    try:
        payload = await retrieval_worker_payload(current)
    except Exception as exc:
        failure_reason = f"retrieval_worker_runtime_error:{type(exc).__name__}"
        return {
            "current_phase": PHASE_FAILED,
            "active_worker": "retrieval_worker",
            "turn_trace": {
                "agentic_runtime": {
                    "current_stage": PHASE_RETRIEVAL,
                    "current_agent": "retrieval_worker",
                    "selected_skills": list(current.get("selected_skills") or []),
                    "failure_point": failure_reason,
                }
            },
            "tool_trace": _tool_trace("retrieval_worker", status="failed", failure_reason=failure_reason),
            "last_worker_result": build_worker_result(
                worker_name="retrieval_worker",
                status="failed",
                phase_entered=PHASE_RETRIEVAL,
                phase_exited=PHASE_FAILED,
                failure_reason=failure_reason,
            ),
        }

    merged = merge_state_patch(current, payload)
    checkpoint = _pick_business_checkpoint(merged)
    candidate_records = _candidate_records_from_state(merged)
    update = deepcopy(payload)
    update["current_phase"] = PHASE_CHECKPOINT if checkpoint else PHASE_RETRIEVAL
    update["active_worker"] = "retrieval_worker"
    update["tool_trace"] = _tool_trace("retrieval_worker", status="success")
    update["last_worker_result"] = build_worker_result(
        worker_name="retrieval_worker",
        status="success" if payload else "no_effect",
        phase_entered=PHASE_RETRIEVAL,
        phase_exited=PHASE_CHECKPOINT if checkpoint else PHASE_RETRIEVAL,
        candidate_kb_delta=candidate_records[:8],
        commit_eligible=False,
        checkpoint_eligible=True,
    )
    if checkpoint:
        update["pending_checkpoint"] = deepcopy(checkpoint)
        update["resume_directive"] = None
    else:
        followup_directive = derive_followup_resume_directive({**current, **update})
        if followup_directive:
            update["resume_directive"] = followup_directive
            update["current_phase"] = PHASE_RESUME
    return update


def _route_after_retrieval(state: SupervisorSessionState) -> str:
    if _as_dict(state.get("pending_checkpoint")):
        return "checkpoint"
    worker_result = _as_dict(state.get("last_worker_result"))
    if str(worker_result.get("status") or "").strip() == "failed":
        return "failed"
    if _as_dict(state.get("resume_directive")):
        return "resume"
    return "composition_worker"


async def _run_resume_node(state: SupervisorSessionState) -> dict[str, Any]:
    directive = _as_dict(state.get("resume_directive"))
    preferred_worker = str(directive.get("preferred_worker") or "retrieval_worker").strip() or "retrieval_worker"
    return {
        "current_phase": PHASE_RESUME,
        "active_worker": preferred_worker,
    }


def _route_from_resume(state: SupervisorSessionState) -> str:
    directive = _as_dict(state.get("resume_directive"))
    preferred_worker = str(directive.get("preferred_worker") or "").strip()
    if preferred_worker == "composition_worker":
        return "composition_worker"
    if preferred_worker == "critique_worker":
        return "critique_worker"
    return "retrieval_worker"


async def _run_composition_node(state: SupervisorSessionState, config: RunnableConfig | None = None) -> dict[str, Any]:
    current = dict(state)
    try:
        payload = await composition_worker_payload(current)
    except Exception as exc:
        failure_reason = f"composition_worker_runtime_error:{type(exc).__name__}"
        return {
            "current_phase": PHASE_FAILED,
            "active_worker": "composition_worker",
            "turn_trace": {
                "agentic_runtime": {
                    "current_stage": PHASE_COMPOSITION,
                    "current_agent": "composition_worker",
                    "selected_skills": list(current.get("selected_skills") or []),
                    "failure_point": failure_reason,
                }
            },
            "tool_trace": _tool_trace("composition_worker", status="failed", failure_reason=failure_reason),
            "last_worker_result": build_worker_result(
                worker_name="composition_worker",
                status="failed",
                phase_entered=PHASE_COMPOSITION,
                phase_exited=PHASE_FAILED,
                failure_reason=failure_reason,
            ),
        }

    changed_blocks = [item for item in (((payload.get("turn_trace") or {}).get("changed_blocks")) or []) if isinstance(item, dict)]
    note_document = payload.get("note_document") if isinstance(payload.get("note_document"), dict) else {}
    assets_delta = [item for item in ((note_document or {}).get("assets") or []) if isinstance(item, dict)]
    failure_reason = "" if (changed_blocks or assets_delta) else "composition_no_effect"
    update = deepcopy(payload)
    update["current_phase"] = PHASE_COMPOSITION
    update["active_worker"] = "composition_worker"
    update["tool_trace"] = _tool_trace(
        "composition_worker",
        status="success" if (changed_blocks or assets_delta) else "failed",
        failure_reason=failure_reason,
    )
    update["last_worker_result"] = build_worker_result(
        worker_name="composition_worker",
        status="success" if (changed_blocks or assets_delta) else "failed",
        phase_entered=PHASE_COMPOSITION,
        phase_exited=PHASE_COMPOSITION if (changed_blocks or assets_delta) else PHASE_FAILED,
        changed_blocks=changed_blocks,
        assets_delta=assets_delta[:6],
        failure_reason=failure_reason,
    )
    return update


def _route_after_composition(state: SupervisorSessionState) -> str:
    worker_result = _as_dict(state.get("last_worker_result"))
    if str(worker_result.get("status") or "").strip() == "failed":
        return "failed"
    if _as_dict(state.get("pending_checkpoint")):
        return "checkpoint"
    return "critique_worker"


async def _run_critique_node(state: SupervisorSessionState, config: RunnableConfig | None = None) -> dict[str, Any]:
    current = dict(state)
    try:
        payload = await critique_worker_payload(current)
    except Exception as exc:
        failure_reason = f"critique_worker_runtime_error:{type(exc).__name__}"
        return {
            "current_phase": PHASE_FAILED,
            "active_worker": "critique_worker",
            "turn_trace": {
                "agentic_runtime": {
                    "current_stage": PHASE_CRITIQUE,
                    "current_agent": "critique_worker",
                    "selected_skills": list(current.get("selected_skills") or []),
                    "failure_point": failure_reason,
                }
            },
            "tool_trace": _tool_trace("critique_worker", status="failed", failure_reason=failure_reason),
            "last_worker_result": build_worker_result(
                worker_name="critique_worker",
                status="failed",
                phase_entered=PHASE_CRITIQUE,
                phase_exited=PHASE_FAILED,
                failure_reason=failure_reason,
                commit_eligible=False,
                checkpoint_eligible=False,
            ),
        }

    feedback = payload.get("critique_feedback") if isinstance(payload.get("critique_feedback"), dict) else {}
    update = deepcopy(payload)
    update["current_phase"] = PHASE_CRITIQUE
    update["active_worker"] = "critique_worker"
    update["tool_trace"] = _tool_trace("critique_worker", status="success" if feedback else "no_effect")
    update["last_worker_result"] = build_worker_result(
        worker_name="critique_worker",
        status="success" if feedback else "no_effect",
        phase_entered=PHASE_CRITIQUE,
        phase_exited=PHASE_CRITIQUE,
        commit_eligible=False,
        checkpoint_eligible=False,
    )
    return update


def _route_after_critique(state: SupervisorSessionState) -> str:
    worker_result = _as_dict(state.get("last_worker_result"))
    if str(worker_result.get("status") or "").strip() == "failed":
        return "failed"
    if _as_dict(state.get("pending_checkpoint")):
        return "checkpoint"
    return "commit"


async def _run_commit_node(state: SupervisorSessionState, config: RunnableConfig | None = None) -> dict[str, Any]:
    current = dict(state)
    note_document = current.get("note_document") if isinstance(current.get("note_document"), dict) else build_note_document_from_state(current)
    quality_patch = apply_artifact_quality_fixes({**current, "note_document": note_document})
    next_note_document = quality_patch.get("note_document") if isinstance(quality_patch.get("note_document"), dict) else note_document
    artifact_quality = quality_patch.get("artifact_quality") if isinstance(quality_patch.get("artifact_quality"), dict) else {}
    autofix_changed_blocks = [
        item for item in (quality_patch.get("autofix_changed_blocks") or [])
        if isinstance(item, dict)
    ]

    turn_trace = deepcopy(_as_dict(current.get("turn_trace")))
    existing_changed_blocks = [item for item in _as_list(turn_trace.get("changed_blocks")) if isinstance(item, dict)]
    turn_trace["changed_blocks"] = _merge_changed_blocks(existing_changed_blocks, autofix_changed_blocks)

    next_last_worker_result = deepcopy(_as_dict(current.get("last_worker_result")))
    if artifact_quality and not bool(artifact_quality.get("passed")) and str(next_last_worker_result.get("worker_name") or "").strip() == "composition_worker":
        next_last_worker_result["status"] = "failed"
        next_last_worker_result["failure_reason"] = str(artifact_quality.get("failure_reason") or "artifact_quality_failed").strip()
        next_last_worker_result["commit_eligible"] = False

    enriched_state = {
        **current,
        "note_document": next_note_document,
        "turn_trace": turn_trace,
        "artifact_quality": artifact_quality,
        "last_worker_result": next_last_worker_result or current.get("last_worker_result"),
    }

    revision_plan = build_revision_plan(enriched_state)
    revision_result = build_revision_result({**enriched_state, "revision_plan": revision_plan})
    revision_result = reconcile_revision_result(revision_result, turn_trace=turn_trace)
    revision_status = build_revision_status({**enriched_state, "revision_plan": revision_plan, "revision_result": revision_result})

    turn_trace["revision"] = {
        "status": revision_status.get("status"),
        "reason": revision_plan.get("reason"),
        "scope": revision_plan.get("scope"),
        "target_block_id": revision_plan.get("target_block_id"),
        "changed_blocks": revision_result.get("changed_blocks") or [],
        "failure_reason": revision_result.get("failure_reason") or "",
    }
    turn_trace["artifact_quality"] = deepcopy(artifact_quality)
    turn_trace["agentic_runtime"] = {
        "current_stage": PHASE_COMMIT,
        "current_agent": "supervisor_agent",
        "selected_skills": list(current.get("selected_skills") or []),
        "failure_point": str((next_last_worker_result or {}).get("failure_reason") or "").strip(),
        "knowledge_version": get_knowledge_version(current),
    }

    configurable = ((config or {}).get("configurable") or {}) if isinstance(config, dict) else {}
    checkpoint_id = str(configurable.get("checkpoint_id") or "")
    thread_id = str(configurable.get("thread_id") or "")
    snapshot_id = f"snapshot_{uuid4().hex[:16]}"

    commit_state = {
        **enriched_state,
        "revision_plan": revision_plan,
        "revision_result": revision_result,
        "revision_status": revision_status,
        "turn_trace": turn_trace,
    }
    artifact_patch = {
        "artifact": ensure_artifact_manifest(commit_state),
        "artifact_version": current.get("artifact_version") if isinstance(current.get("artifact_version"), dict) else {},
        "version_history_head": current.get("version_history_head") if isinstance(current.get("version_history_head"), list) else [],
    }
    committed = should_commit_artifact_version(commit_state)
    if committed:
        artifact_patch.update(
            build_artifact_patch(
                commit_state,
                snapshot_id=snapshot_id,
                checkpoint_id=checkpoint_id,
                thread_id=thread_id,
            )
        )

    next_phase = PHASE_DONE if committed else (PHASE_FAILED if artifact_quality and not bool(artifact_quality.get("passed")) else PHASE_COMMIT)
    return {
        "note_document": next_note_document,
        "artifact_quality": artifact_quality,
        "revision_plan": revision_plan,
        "revision_result": revision_result,
        "revision_status": revision_status,
        "turn_trace": turn_trace,
        "last_worker_result": next_last_worker_result or current.get("last_worker_result"),
        "resume_directive": None,
        "current_phase": next_phase,
        "active_worker": "supervisor_agent" if next_phase in {PHASE_COMMIT, PHASE_DONE} else str(current.get("active_worker") or "supervisor_agent"),
        **artifact_patch,
    }


async def _run_checkpoint_node(state: SupervisorSessionState) -> dict[str, Any]:
    return {
        "current_phase": PHASE_CHECKPOINT,
        "active_worker": "checkpoint",
    }


async def _run_failed_node(state: SupervisorSessionState) -> dict[str, Any]:
    return {
        "current_phase": PHASE_FAILED,
        "active_worker": str(state.get("active_worker") or "supervisor_agent"),
    }


def build_supervisor_runtime(checkpointer, store: BaseStore | None = None):
    graph = StateGraph(SupervisorSessionState)
    graph.add_node("supervisor_agent", _run_intent_node)
    graph.add_node("retrieval_worker", _run_retrieval_node)
    graph.add_node("resume", _run_resume_node)
    graph.add_node("composition_worker", _run_composition_node)
    graph.add_node("critique_worker", _run_critique_node)
    graph.add_node("commit", _run_commit_node)
    graph.add_node("checkpoint", _run_checkpoint_node)
    graph.add_node("failed", _run_failed_node)

    graph.add_edge(START, "supervisor_agent")
    graph.add_conditional_edges(
        "supervisor_agent",
        _route_from_supervisor,
        {
            "retrieval_worker": "retrieval_worker",
            "composition_worker": "composition_worker",
            "critique_worker": "critique_worker",
            "resume": "resume",
            "checkpoint": "checkpoint",
            "failed": "failed",
        },
    )
    graph.add_conditional_edges(
        "retrieval_worker",
        _route_after_retrieval,
        {
            "checkpoint": "checkpoint",
            "resume": "resume",
            "composition_worker": "composition_worker",
            "failed": "failed",
        },
    )
    graph.add_conditional_edges(
        "resume",
        _route_from_resume,
        {
            "retrieval_worker": "retrieval_worker",
            "composition_worker": "composition_worker",
            "critique_worker": "critique_worker",
        },
    )
    graph.add_conditional_edges(
        "composition_worker",
        _route_after_composition,
        {
            "checkpoint": "checkpoint",
            "critique_worker": "critique_worker",
            "failed": "failed",
        },
    )
    graph.add_conditional_edges(
        "critique_worker",
        _route_after_critique,
        {
            "checkpoint": "checkpoint",
            "commit": "commit",
            "failed": "failed",
        },
    )
    graph.add_edge("commit", END)
    graph.add_edge("checkpoint", END)
    graph.add_edge("failed", END)
    return graph.compile(checkpointer=checkpointer, store=store)

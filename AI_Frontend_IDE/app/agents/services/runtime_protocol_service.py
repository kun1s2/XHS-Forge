from __future__ import annotations

from copy import deepcopy
from typing import Any


PHASE_INTENT = "intent"
PHASE_RETRIEVAL = "retrieve"
PHASE_COMPOSITION = "compose"
PHASE_CRITIQUE = "critique"
PHASE_CHECKPOINT = "checkpoint"
PHASE_RESUME = "resume"
PHASE_COMMIT = "commit"
PHASE_DONE = "done"
PHASE_FAILED = "failed"

_PHASE_ALIASES = {
    "intent_decision": PHASE_INTENT,
    "intent": PHASE_INTENT,
    "retrieval": PHASE_RETRIEVAL,
    "retrieve": PHASE_RETRIEVAL,
    "composition": PHASE_COMPOSITION,
    "compose": PHASE_COMPOSITION,
    "critique": PHASE_CRITIQUE,
    "checkpoint": PHASE_CHECKPOINT,
    "resume": PHASE_RESUME,
    "commit": PHASE_COMMIT,
    "done": PHASE_DONE,
    "failed": PHASE_FAILED,
}

_PHASE_TRANSITIONS = {
    PHASE_INTENT: {PHASE_RETRIEVAL, PHASE_FAILED},
    PHASE_RETRIEVAL: {PHASE_CHECKPOINT, PHASE_RESUME, PHASE_COMPOSITION, PHASE_FAILED},
    PHASE_CHECKPOINT: {PHASE_RESUME, PHASE_FAILED},
    PHASE_RESUME: {PHASE_RETRIEVAL, PHASE_COMPOSITION, PHASE_FAILED},
    PHASE_COMPOSITION: {PHASE_CRITIQUE, PHASE_COMMIT, PHASE_FAILED},
    PHASE_CRITIQUE: {PHASE_COMMIT, PHASE_CHECKPOINT, PHASE_FAILED},
    PHASE_COMMIT: {PHASE_DONE, PHASE_FAILED},
    PHASE_DONE: {PHASE_INTENT, PHASE_RETRIEVAL, PHASE_COMPOSITION, PHASE_CRITIQUE, PHASE_RESUME, PHASE_FAILED},
    PHASE_FAILED: {PHASE_INTENT, PHASE_RETRIEVAL, PHASE_RESUME, PHASE_COMPOSITION},
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _has_visible_blocks(state: dict[str, Any] | None) -> bool:
    note_document = _as_dict((state or {}).get("note_document"))
    return bool(_as_list(note_document.get("blocks")))


def normalize_phase_name(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return _PHASE_ALIASES.get(raw, PHASE_INTENT)


def transition_phase(current_phase: Any, requested_phase: Any) -> str:
    current = normalize_phase_name(current_phase)
    requested = normalize_phase_name(requested_phase)
    if requested == current:
        return current
    if requested in _PHASE_TRANSITIONS.get(current, set()):
        return requested
    if current == PHASE_CHECKPOINT and requested in {PHASE_RETRIEVAL, PHASE_COMPOSITION}:
        return PHASE_RESUME
    if current == PHASE_RESUME and requested in {PHASE_CRITIQUE, PHASE_COMMIT, PHASE_DONE}:
        return PHASE_COMPOSITION
    return requested


def _resume_entity_anchor(state: dict[str, Any] | None) -> str:
    state = state or {}
    retrieved_knowledge = _as_dict(state.get("retrieved_knowledge"))
    retrieval_summary = _as_dict(retrieved_knowledge.get("retrieval_summary"))
    artifact = _as_dict(state.get("artifact"))
    note_document = _as_dict(state.get("note_document"))
    document_meta = _as_dict(note_document.get("document_meta"))
    candidates = [
        str(retrieved_knowledge.get("entity_name") or "").strip(),
        str(retrieval_summary.get("entity_name") or "").strip(),
        str(artifact.get("title") or "").strip(),
        str(document_meta.get("title") or "").strip(),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return "当前持续笔记"


def build_worker_result(
    *,
    worker_name: str,
    status: str,
    phase_entered: str,
    phase_exited: str | None = None,
    changed_blocks: list[dict[str, Any]] | None = None,
    assets_delta: list[dict[str, Any]] | None = None,
    candidate_kb_delta: list[dict[str, Any]] | None = None,
    failure_reason: str | None = None,
    commit_eligible: bool | None = None,
    checkpoint_eligible: bool | None = None,
) -> dict[str, Any]:
    safe_changed_blocks = [deepcopy(item) for item in (changed_blocks or []) if isinstance(item, dict)]
    safe_assets_delta = [deepcopy(item) for item in (assets_delta or []) if isinstance(item, dict)]
    safe_candidate_kb_delta = [deepcopy(item) for item in (candidate_kb_delta or []) if isinstance(item, dict)]
    normalized_status = str(status or "idle").strip() or "idle"
    normalized_failure_reason = str(failure_reason or "").strip()
    resolved_commit_eligible = bool(commit_eligible) if commit_eligible is not None else bool(
        normalized_status == "success" and (safe_changed_blocks or safe_assets_delta)
    )
    resolved_checkpoint_eligible = bool(checkpoint_eligible) if checkpoint_eligible is not None else bool(
        worker_name == "retrieval_worker"
    )
    return {
        "worker_name": worker_name,
        "status": normalized_status,
        "phase_entered": normalize_phase_name(phase_entered or worker_name),
        "phase_exited": normalize_phase_name(phase_exited or phase_entered or worker_name),
        "changed_blocks": safe_changed_blocks,
        "assets_delta": safe_assets_delta,
        "candidate_kb_delta": safe_candidate_kb_delta,
        "failure_reason": normalized_failure_reason,
        "commit_eligible": resolved_commit_eligible,
        "checkpoint_eligible": resolved_checkpoint_eligible,
    }


def build_checkpoint_resume_directive(
    *,
    state: dict[str, Any] | None = None,
    checkpoint_type: str,
    decision_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision_payload = _as_dict(decision_payload)
    decision_choice = str(decision_payload.get("decision") or "").strip()
    state = state or {}
    entity_anchor = _resume_entity_anchor(state)
    has_visible_blocks = _has_visible_blocks(state)

    if checkpoint_type == "structure_checkpoint":
        preferred_worker = "retrieval_worker"
        resume_query = f"已确认页面骨架方向，继续围绕「{entity_anchor}」补齐关键事实并开始搭建持续笔记，不要再次请求结构确认。"
    elif checkpoint_type in {
        "knowledge_review_checkpoint",
        "truth_mode_checkpoint",
    }:
        preferred_worker = "composition_worker"
        resume_query = f"已完成这轮知识或真实性确认，继续基于当前已确认事实把「{entity_anchor}」落成页面，不要重复停在同一个确认点。"
    elif checkpoint_type == "fact_gap_checkpoint":
        if decision_choice == "continue_research":
            preferred_worker = "retrieval_worker"
            resume_query = f"还存在关键事实缺口，继续围绕「{entity_anchor}」补搜并补证据，不要重新发同一张缺口确认卡。"
        else:
            preferred_worker = "composition_worker"
            resume_query = f"已确认先按保守策略继续，继续把「{entity_anchor}」落成页面，不要再次请求同一张缺口确认卡。"
    elif checkpoint_type == "fact_conflict_checkpoint":
        if decision_choice.startswith("confirm::"):
            preferred_worker = "composition_worker"
            resume_query = f"冲突事实已选定，继续把「{entity_anchor}」整理成页面结论，不要再次请求同一条冲突确认。"
        elif decision_choice == "keep_cautious":
            preferred_worker = "composition_worker"
            resume_query = f"这轮先保持保守表达，继续完成「{entity_anchor}」的页面生成，不要再次请求同一条冲突确认。"
        else:
            preferred_worker = "retrieval_worker"
            resume_query = f"继续围绕「{entity_anchor}」补充冲突事实的证据，再继续推进页面。"
    elif checkpoint_type == "asset_checkpoint":
        if decision_choice == "search_images_for_cover":
            preferred_worker = "retrieval_worker"
            resume_query = f"继续为「{entity_anchor}」搜索更贴题的图片素材，再把素材落到当前持续笔记中。"
        else:
            preferred_worker = "composition_worker"
            resume_query = f"已确认素材方案，继续把素材落到「{entity_anchor}」的持续笔记中，不要再次请求同一个素材确认。"
    else:
        preferred_worker = "composition_worker" if has_visible_blocks else "retrieval_worker"
        resume_query = f"已完成这轮确认，继续推进「{entity_anchor}」当前的持续笔记。"

    return {
        "source": checkpoint_type,
        "preferred_worker": preferred_worker,
        "resume_query": resume_query,
        "decision": decision_choice,
    }


def build_revision_resume_directive(
    *,
    state: dict[str, Any] | None = None,
    revision_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = state or {}
    plan = _as_dict(revision_plan)
    entity_anchor = _resume_entity_anchor(state)
    target_block_id = str(plan.get("target_block_id") or "").strip()
    reason = str(plan.get("reason") or "").strip()
    expected_effect = str(plan.get("expected_effect") or "").strip()
    plan_prompt = str(plan.get("prompt") or "").strip()
    operation_type = str(plan.get("operation_type") or "").strip().lower()
    preferred_worker = "retrieval_worker" if operation_type == "asset_edit" else "composition_worker"

    if preferred_worker == "retrieval_worker":
        if plan_prompt:
            resume_query = plan_prompt
        else:
            resume_query = f"继续为「{entity_anchor}」补图并把素材落到当前持续笔记中，不要重新走复盘或泛化检索。"
    else:
        scope_hint = f"优先修改区块 {target_block_id}。" if target_block_id else "优先沿当前结构继续收口。"
        detail_parts = [part for part in (reason, expected_effect) if part]
        detail_line = " ".join(detail_parts).strip()
        resume_query = (
            f"继续优化「{entity_anchor}」当前持续笔记，{scope_hint}"
            f"{detail_line or '按这轮修订建议继续把内容收紧，不要重新起草，也不要重新进入检索流程。'}"
        )

    return {
        "source": "revision_action",
        "preferred_worker": preferred_worker,
        "resume_query": resume_query,
        "decision": str(plan.get("recipe_id") or "apply_revision").strip() or "apply_revision",
    }


def derive_phase_from_state(state: dict[str, Any]) -> str:
    pending_checkpoint = _as_dict(state.get("pending_checkpoint"))
    if pending_checkpoint:
        return PHASE_CHECKPOINT

    resume_directive = _as_dict(state.get("resume_directive"))
    if resume_directive:
        return PHASE_RESUME

    artifact_quality = _as_dict(state.get("artifact_quality"))
    if artifact_quality and not bool(artifact_quality.get("passed")):
        return PHASE_FAILED

    worker_result = _as_dict(state.get("last_worker_result"))
    worker_name = str(worker_result.get("worker_name") or "").strip()
    status = str(worker_result.get("status") or "").strip()
    if status == "failed":
        return PHASE_FAILED
    if worker_name == "retrieval_worker":
        return PHASE_RETRIEVAL
    if worker_name == "composition_worker":
        return PHASE_COMPOSITION
    if worker_name == "critique_worker":
        return PHASE_CRITIQUE
    current_phase = normalize_phase_name(state.get("current_phase"))
    if current_phase == PHASE_COMMIT:
        return PHASE_COMMIT
    if current_phase == PHASE_DONE:
        return PHASE_DONE
    return current_phase or PHASE_INTENT


def derive_followup_resume_directive(state: dict[str, Any]) -> dict[str, Any] | None:
    pending_checkpoint = _as_dict(state.get("pending_checkpoint"))
    if pending_checkpoint:
        return None

    existing_resume = _as_dict(state.get("resume_directive"))
    if existing_resume:
        return existing_resume

    worker_result = _as_dict(state.get("last_worker_result"))
    if str(worker_result.get("worker_name") or "").strip() != "retrieval_worker":
        return None
    if str(worker_result.get("status") or "").strip() != "success":
        return None
    if str(worker_result.get("failure_reason") or "").strip():
        return None

    note_document = _as_dict(state.get("note_document"))
    has_blocks = bool(_as_list(note_document.get("blocks")))
    if has_blocks:
        return None

    return {
        "source": "protocol_followup",
        "preferred_worker": "composition_worker",
        "resume_query": "结构和知识已经准备好，继续把持续笔记落成可见页面，不要停在分析阶段。",
        "decision": "auto_followup",
    }


def should_commit_artifact_version(state: dict[str, Any]) -> bool:
    current_phase = derive_phase_from_state(state)
    artifact_version = _as_dict(state.get("artifact_version"))
    note_document = _as_dict(state.get("note_document"))
    has_existing_version = bool(str(artifact_version.get("version_id") or "").strip())
    has_blocks = bool(_as_list(note_document.get("blocks")))
    if current_phase not in {PHASE_COMPOSITION, PHASE_CRITIQUE, PHASE_COMMIT, PHASE_DONE}:
        if has_existing_version or not has_blocks:
            return False

    pending_checkpoint = _as_dict(state.get("pending_checkpoint"))
    if pending_checkpoint:
        return False

    artifact_quality = _as_dict(state.get("artifact_quality"))
    if artifact_quality and not bool(artifact_quality.get("passed")):
        return False

    revision_result = _as_dict(state.get("revision_result"))
    turn_trace = _as_dict(state.get("turn_trace"))
    trace_changed_blocks = [item for item in _as_list(turn_trace.get("changed_blocks")) if isinstance(item, dict)]
    revision_changed_blocks = [item for item in _as_list(revision_result.get("changed_blocks")) if isinstance(item, dict)]
    revision_assets_delta = [item for item in _as_list(revision_result.get("assets_delta")) if isinstance(item, dict)]
    if str(revision_result.get("status") or "").strip() == "success":
        if revision_assets_delta:
            return True
        if revision_changed_blocks and (trace_changed_blocks or not turn_trace):
            return True

    composition_trace = _as_dict(turn_trace.get("composition_worker"))
    if trace_changed_blocks:
        return True
    if str(composition_trace.get("skill_execution_result") or "").strip() == "success":
        return True

    worker_result = _as_dict(state.get("last_worker_result"))
    if worker_result:
        if not bool(worker_result.get("commit_eligible")):
            return False
        if str(worker_result.get("worker_name") or "").strip() != "composition_worker":
            return False
        if str(worker_result.get("status") or "").strip() != "success":
            return False
        return True

    return bool(not has_existing_version and has_blocks)


def phase_after_commit(*, committed: bool, failed: bool = False) -> str:
    if failed:
        return PHASE_FAILED
    if committed:
        return PHASE_DONE
    return PHASE_COMMIT


__all__ = [
    "PHASE_CHECKPOINT",
    "PHASE_COMMIT",
    "PHASE_COMPOSITION",
    "PHASE_CRITIQUE",
    "PHASE_DONE",
    "PHASE_FAILED",
    "PHASE_INTENT",
    "PHASE_RESUME",
    "PHASE_RETRIEVAL",
    "build_checkpoint_resume_directive",
    "build_revision_resume_directive",
    "build_worker_result",
    "derive_followup_resume_directive",
    "derive_phase_from_state",
    "normalize_phase_name",
    "phase_after_commit",
    "should_commit_artifact_version",
    "transition_phase",
]


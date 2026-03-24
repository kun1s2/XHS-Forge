from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import uuid4


ARTIFACT_TYPE = "purchase_decision_note"
ARTIFACT_STATUS = "active"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _document_title(state: dict[str, Any]) -> str:
    note_document = _as_dict(state.get("note_document"))
    meta = _as_dict(note_document.get("document_meta"))
    title = str(meta.get("title") or "").strip()
    if title:
        return title
    retrieved_knowledge = _as_dict(state.get("retrieved_knowledge"))
    entity_name = str(retrieved_knowledge.get("entity_name") or "").strip()
    if entity_name:
        return f"{entity_name} 购买决策档案"
    return "数码购买决策档案"


def get_knowledge_version(state: dict[str, Any]) -> str:
    retrieved_knowledge = _as_dict(state.get("retrieved_knowledge"))
    for candidate in (
        _as_dict(retrieved_knowledge.get("session_kb")).get("knowledge_version"),
        retrieved_knowledge.get("knowledge_version"),
        _as_dict(state.get("artifact_version")).get("knowledge_version"),
    ):
        text = str(candidate or "").strip()
        if text:
            return text
    return "session-kb::0"


def ensure_artifact_manifest(state: dict[str, Any]) -> dict[str, Any]:
    existing = deepcopy(_as_dict(state.get("artifact")))
    artifact_id = str(existing.get("artifact_id") or "").strip() or f"artifact_{uuid4().hex[:16]}"
    snapshot_id = str(existing.get("current_snapshot_id") or "").strip()
    version_id = str(existing.get("current_version_id") or "").strip()
    artifact = {
        **existing,
        "artifact_id": artifact_id,
        "artifact_type": ARTIFACT_TYPE,
        "current_version_id": version_id,
        "current_snapshot_id": snapshot_id,
        "title": str(existing.get("title") or "").strip() or _document_title(state),
        "status": str(existing.get("status") or ARTIFACT_STATUS).strip() or ARTIFACT_STATUS,
    }
    return artifact


def _normalized_changed_blocks(state: dict[str, Any]) -> list[dict[str, Any]]:
    revision_result = _as_dict(state.get("revision_result"))
    if revision_result.get("changed_blocks"):
        return [item for item in _as_list(revision_result.get("changed_blocks")) if isinstance(item, dict)]
    turn_trace = _as_dict(state.get("turn_trace"))
    return [item for item in _as_list(turn_trace.get("changed_blocks")) if isinstance(item, dict)]


def _normalized_assets_delta(state: dict[str, Any]) -> list[dict[str, Any]]:
    revision_result = _as_dict(state.get("revision_result"))
    if revision_result.get("assets_delta"):
        return [item for item in _as_list(revision_result.get("assets_delta")) if isinstance(item, dict)]
    last_worker = _as_dict(state.get("last_worker_result"))
    return [item for item in _as_list(last_worker.get("assets_delta")) if isinstance(item, dict)]


def infer_revision_reason(state: dict[str, Any]) -> str:
    for candidate in (
        _as_dict(state.get("revision_plan")).get("reason"),
        _as_dict(state.get("revision_result")).get("revision_reason"),
        _as_dict(state.get("checkpoint_decision")).get("custom_note"),
        _as_dict(state.get("last_worker_result")).get("failure_reason"),
    ):
        text = str(candidate or "").strip()
        if text:
            return text
    messages = _as_list(state.get("main_messages") or state.get("messages"))
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()[:200]
    return "turn_update"


def build_artifact_version(state: dict[str, Any], *, snapshot_id: str, checkpoint_id: str = "") -> dict[str, Any]:
    artifact = ensure_artifact_manifest(state)
    previous_version = _as_dict(state.get("artifact_version"))
    version_id = f"version_{uuid4().hex[:16]}"
    changed_blocks = deepcopy(_normalized_changed_blocks(state))
    assets_delta = deepcopy(_normalized_assets_delta(state))
    return {
        "version_id": version_id,
        "parent_version_id": str(previous_version.get("version_id") or "").strip() or None,
        "snapshot_id": snapshot_id,
        "checkpoint_id": checkpoint_id or None,
        "revision_reason": infer_revision_reason(state),
        "changed_blocks": changed_blocks,
        "assets_delta": assets_delta,
        "knowledge_version": get_knowledge_version(state),
        "created_at": datetime.now().isoformat(),
        "artifact_id": artifact["artifact_id"],
    }


def build_version_history_head(
    state: dict[str, Any],
    *,
    latest_version: dict[str, Any],
    limit: int = 8,
) -> list[dict[str, Any]]:
    head: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in [latest_version, *_as_list(state.get("version_history_head"))]:
        if not isinstance(candidate, dict):
            continue
        version_id = str(candidate.get("version_id") or "").strip()
        if not version_id or version_id in seen:
            continue
        seen.add(version_id)
        head.append(deepcopy(candidate))
        if len(head) >= limit:
            break
    return head


def build_artifact_patch(state: dict[str, Any], *, snapshot_id: str, checkpoint_id: str = "") -> dict[str, Any]:
    artifact = ensure_artifact_manifest(state)
    version = build_artifact_version(state, snapshot_id=snapshot_id, checkpoint_id=checkpoint_id)
    artifact["current_version_id"] = version["version_id"]
    artifact["current_snapshot_id"] = snapshot_id
    artifact["title"] = _document_title(state)
    return {
        "artifact": artifact,
        "artifact_version": version,
        "version_history_head": build_version_history_head(state, latest_version=version),
    }

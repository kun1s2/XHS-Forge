from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agents.services.artifact_service import ensure_artifact_manifest
from app.agents.services.revision_service import build_revision_plan, build_revision_status
from app.agents.services.runtime_protocol_service import PHASE_INTENT, normalize_phase_name
from app.core.note_document import build_note_document_from_state


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_session_runtime_defaults(state: dict[str, Any]) -> dict[str, Any]:
    note_document = _as_dict(state.get("note_document")) or build_note_document_from_state(state)
    artifact = ensure_artifact_manifest({**state, "note_document": note_document})
    existing_revision_plan = _as_dict(state.get("revision_plan"))
    existing_revision_result = _as_dict(state.get("revision_result"))
    existing_revision_status = _as_dict(state.get("revision_status"))
    critique_feedback = _as_dict(state.get("critique_feedback"))
    has_visible_blocks = bool((note_document.get("blocks") or []))
    has_artifact_version = bool(str(_as_dict(state.get("artifact_version")).get("version_id") or "").strip())
    has_revision_signal = bool(
        existing_revision_plan
        or existing_revision_result
        or existing_revision_status
        or (critique_feedback.get("action_recipes") or [])
    )
    if existing_revision_plan:
        revision_plan = existing_revision_plan
    elif has_revision_signal and (has_visible_blocks or has_artifact_version):
        revision_plan = build_revision_plan({**state, "note_document": note_document})
    else:
        revision_plan = {}
    if existing_revision_status:
        revision_status = existing_revision_status
    elif (revision_plan or existing_revision_result) and (has_visible_blocks or has_artifact_version):
        revision_status = build_revision_status(
            {
                **state,
                "note_document": note_document,
                "revision_plan": revision_plan,
                "revision_result": existing_revision_result,
            }
        )
    else:
        revision_status = {}
    defaults = {
        "active_panel": str(state.get("active_panel") or "main"),
        "active_archetype": str(state.get("active_archetype") or "seeding"),
        "scenarios": list(state.get("scenarios") or ["seeding"]),
        "creator_persona": str(state.get("creator_persona") or "硬核数码博主"),
        "current_phase": normalize_phase_name(state.get("current_phase") or PHASE_INTENT),
        "active_worker": state.get("active_worker") or "supervisor",
        "note_document": note_document,
        "artifact": artifact,
        "artifact_version": deepcopy(_as_dict(state.get("artifact_version"))),
        "version_history_head": deepcopy(state.get("version_history_head") or []),
        "revision_plan": revision_plan,
        "revision_result": deepcopy(existing_revision_result),
        "revision_status": revision_status,
    }
    return defaults

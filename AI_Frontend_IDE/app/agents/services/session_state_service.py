from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agents.services.artifact_service import ensure_artifact_manifest
from app.agents.services.revision_service import build_revision_plan, build_revision_status
from app.core.note_document import build_note_document_from_state


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_session_runtime_defaults(state: dict[str, Any]) -> dict[str, Any]:
    note_document = _as_dict(state.get("note_document")) or build_note_document_from_state(state)
    artifact = ensure_artifact_manifest({**state, "note_document": note_document})
    revision_plan = _as_dict(state.get("revision_plan")) or build_revision_plan({**state, "note_document": note_document})
    revision_status = _as_dict(state.get("revision_status")) or build_revision_status({**state, "revision_plan": revision_plan})
    defaults = {
        "active_panel": str(state.get("active_panel") or "main"),
        "active_archetype": str(state.get("active_archetype") or "seeding"),
        "scenarios": list(state.get("scenarios") or ["seeding"]),
        "creator_persona": str(state.get("creator_persona") or "硬核数码博主"),
        "current_phase": str(state.get("current_phase") or "intent_decision"),
        "active_worker": state.get("active_worker") or "supervisor",
        "note_document": note_document,
        "artifact": artifact,
        "artifact_version": deepcopy(_as_dict(state.get("artifact_version"))),
        "version_history_head": deepcopy(state.get("version_history_head") or []),
        "revision_plan": revision_plan,
        "revision_result": deepcopy(_as_dict(state.get("revision_result"))),
        "revision_status": revision_status,
    }
    return defaults


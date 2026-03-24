import sys
from pathlib import Path
from copy import deepcopy


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "AI_Frontend_IDE"

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


from app.core import note_document as _note_document_module


_runtime_build_note_document_from_state = _note_document_module.build_note_document_from_state


def _build_note_document_from_test_state(state: dict | None) -> dict:
    state = state or {}
    note_document = state.get("note_document")
    if isinstance(note_document, dict) and note_document.get("blocks") is not None:
        return _runtime_build_note_document_from_state(state)

    if "document_view" in state or "block_style_map" in state:
        return _note_document_module.build_note_document(
            document_view=deepcopy(state.get("document_view") or {}),
            block_style_map=deepcopy(state.get("block_style_map") or {}),
            image_assets=deepcopy(state.get("image_assets") or []),
            patch_tracks=deepcopy(state.get("patch_tracks") or {}),
            selected_element_id=state.get("selected_element_id"),
            active_panel=state.get("active_panel"),
            scenarios=deepcopy(state.get("scenarios") or []),
            active_archetype=state.get("active_archetype"),
            retrieved_knowledge=deepcopy(state.get("retrieved_knowledge") or {}),
            planner_output=deepcopy(state.get("planner_output") or {}),
        )

    return _runtime_build_note_document_from_state(state)


_note_document_module.build_note_document_from_state = _build_note_document_from_test_state

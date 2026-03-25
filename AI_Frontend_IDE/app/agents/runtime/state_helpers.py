from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.note_document import build_note_document_from_state, update_note_document_block


def merge_image_assets(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Merge image assets, supporting explicit full replacement."""
    safe_left = [item for item in (left or []) if isinstance(item, dict)]
    safe_right = [item for item in (right or []) if isinstance(item, dict)]
    if safe_right and safe_right[0].get("__replace__"):
        return [
            {k: v for k, v in item.items() if k != "__replace__"}
            for item in safe_right[1:]
        ]
    return safe_left + safe_right


def merge_state_patch(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Deep merge a runtime patch, preserving surgical block operations."""
    if not isinstance(left, dict):
        left = {}

    merged = left.copy()
    if not isinstance(right, dict):
        return merged

    runtime_patch = dict(right)

    if "_block_append" in runtime_patch:
        if "blocks" not in merged:
            merged["blocks"] = []
        merged["blocks"].append(runtime_patch["_block_append"])
        runtime_patch.pop("_block_append", None)

    if "_block_insert" in runtime_patch:
        if "blocks" not in merged:
            merged["blocks"] = []
        idx = runtime_patch["_block_insert"].get("index", 0)
        block = runtime_patch["_block_insert"].get("block", {})
        idx = min(max(0, idx), len(merged["blocks"]))
        merged["blocks"].insert(idx, block)
        runtime_patch.pop("_block_insert", None)

    if "_block_remove" in runtime_patch:
        if "blocks" in merged:
            merged["blocks"] = [
                block
                for block in merged["blocks"]
                if block.get("id") != runtime_patch["_block_remove"]
            ]
        runtime_patch.pop("_block_remove", None)

    if "_block_update" in runtime_patch:
        if "blocks" in merged:
            target_id = runtime_patch["_block_update"].get("id")
            for block in merged["blocks"]:
                if block.get("id") == target_id:
                    block.update(runtime_patch["_block_update"].get("data", {}))
        runtime_patch.pop("_block_update", None)

    if runtime_patch.get("_blocks_override"):
        if "blocks" in runtime_patch:
            merged["blocks"] = runtime_patch["blocks"]
        runtime_patch.pop("_blocks_override", None)
        runtime_patch.pop("blocks", None)

    for key, value in runtime_patch.items():
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_state_patch(merged[key], value)
        else:
            merged[key] = value

    return merged


def merge_patch_tracks(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Append patch-track records per block/component key."""
    if not isinstance(left, dict):
        left = {}
    if not isinstance(right, dict):
        return left

    merged = left.copy()
    for key, value in right.items():
        if isinstance(value, list):
            if key in merged and isinstance(merged[key], list):
                merged[key] = merged[key] + value
            else:
                merged[key] = value
    return merged


def merge_turn_anchors(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Upsert turn anchors by (panel, turn_index)."""
    merged: list[dict[str, Any]] = [
        dict(item)
        for item in (left or [])
        if isinstance(item, dict)
    ]

    for candidate in right or []:
        if not isinstance(candidate, dict):
            continue
        panel = str(candidate.get("panel") or "main")
        turn_index = int(candidate.get("turn_index") or 0)
        replaced = False
        for idx, existing in enumerate(merged):
            if (
                str(existing.get("panel") or "main") == panel
                and int(existing.get("turn_index") or 0) == turn_index
            ):
                merged[idx] = dict(candidate)
                replaced = True
                break
        if not replaced:
            merged.append(dict(candidate))
    return merged


def merge_unique_strings(left: list[str] | None, right: list[str] | None) -> list[str]:
    """Merge string lists while keeping order stable and unique."""
    output: list[str] = []
    seen: set[str] = set()
    for candidate in [*(left or []), *(right or [])]:
        value = str(candidate or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def overwrite_state_value(_left: Any, right: Any) -> Any:
    """Allow multiple writes in one LangGraph step while taking the latest value."""
    return deepcopy(right)


def restore_component_version(state: Any, element_id: str, version_index: int) -> dict[str, Any]:
    """Build a rollback patch from patch tracks for a single component."""
    tracks = state.get("patch_tracks", {})
    if element_id not in tracks or version_index >= len(tracks[element_id]):
        return {}

    target_version = tracks[element_id][version_index]
    data_snapshot = target_version.get("data_snapshot")
    if not data_snapshot:
        return {}

    note_document = build_note_document_from_state(state)
    current_block = next(
        (block for block in (note_document.get("blocks") or []) if block.get("id") == element_id),
        {},
    )
    current_component_data = current_block.get("props") or {}
    rollback_patch = data_snapshot.copy()

    for key in current_component_data.keys():
        if key not in data_snapshot:
            rollback_patch[key] = None

    rollback_patch = {k: v for k, v in rollback_patch.items() if v is not None}
    return {
        "note_document": update_note_document_block(
            note_document,
            element_id,
            props=rollback_patch,
        )
    }


__all__ = [
    "merge_image_assets",
    "merge_patch_tracks",
    "merge_state_patch",
    "merge_turn_anchors",
    "merge_unique_strings",
    "overwrite_state_value",
    "restore_component_version",
]

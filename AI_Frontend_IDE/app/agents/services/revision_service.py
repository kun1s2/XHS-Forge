from __future__ import annotations

from copy import deepcopy
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def select_primary_recipe(feedback: dict[str, Any] | None) -> dict[str, Any] | None:
    payload = _as_dict(feedback)
    recipes = [item for item in _as_list(payload.get("action_recipes")) if isinstance(item, dict)]
    if not recipes:
        return None
    for recipe in recipes:
        if str(recipe.get("scope") or "").strip() != "noop" and str(recipe.get("prompt") or "").strip():
            return deepcopy(recipe)
    return deepcopy(recipes[0])


def build_revision_plan(state: dict[str, Any]) -> dict[str, Any]:
    feedback = _as_dict(state.get("critique_feedback"))
    recipe = select_primary_recipe(feedback)
    if not recipe:
        return {}
    scope_name = str(recipe.get("scope") or "global_canvas").strip() or "global_canvas"
    target_block_id = str(state.get("selected_element_id") or "").strip() or None
    note_document = _as_dict(state.get("note_document"))
    target_block_type = ""
    if target_block_id:
        for block in _as_list(note_document.get("blocks")):
            if isinstance(block, dict) and str(block.get("id") or "").strip() == target_block_id:
                target_block_type = str(block.get("type") or "").strip()
                break
    operation_type = "asset_edit" if "image" in scope_name or "asset" in scope_name else "text_edit"
    return {
        "recipe_id": str(recipe.get("scope") or "primary"),
        "label": str(recipe.get("label") or "听取意见"),
        "prompt": str(recipe.get("prompt") or "").strip(),
        "reason": str(recipe.get("why_now") or (feedback.get("suggestions") or ["继续优化当前档案"])[0] or "").strip(),
        "scope": "selected_block" if target_block_id else "global_canvas",
        "target_block_id": target_block_id,
        "target_block_type": target_block_type or None,
        "operation_type": operation_type,
        "allowed_change_surface": [scope_name] if scope_name else [],
        "expected_effect": str(recipe.get("expected_effect") or "").strip(),
        "expected_blocks": [str(item).strip() for item in _as_list(recipe.get("expected_blocks")) if str(item).strip()],
        "primary_recipe": recipe,
    }


def build_revision_result(state: dict[str, Any]) -> dict[str, Any]:
    last_worker_result = _as_dict(state.get("last_worker_result"))
    if not last_worker_result:
        return {}
    worker_name = str(last_worker_result.get("worker_name") or "").strip()
    changed_blocks = deepcopy([item for item in _as_list(last_worker_result.get("changed_blocks")) if isinstance(item, dict)])
    assets_delta = deepcopy([item for item in _as_list(last_worker_result.get("assets_delta")) if isinstance(item, dict)])
    status = str(last_worker_result.get("status") or "idle").strip() or "idle"
    if worker_name not in {"composition_worker", "asset_worker"} and not changed_blocks and not assets_delta:
        status = "idle"
    return {
        "status": status,
        "changed_blocks": changed_blocks,
        "assets_delta": assets_delta,
        "failure_reason": str(last_worker_result.get("failure_reason") or "").strip(),
        "worker_name": worker_name,
        "revision_reason": str(_as_dict(state.get("revision_plan")).get("reason") or "").strip(),
    }


def build_revision_status(state: dict[str, Any]) -> dict[str, Any]:
    feedback = _as_dict(state.get("critique_feedback"))
    primary_recipe = select_primary_recipe(feedback)
    revision_result = build_revision_result(state)
    if primary_recipe:
        status = "ready"
    else:
        status = "idle"
    if revision_result.get("status") == "failed":
        status = "failed"
    elif revision_result.get("status") == "success":
        status = "applied"
    return {
        "status": status,
        "needs_revision": bool(state.get("needs_revision")),
        "primary_recipe": primary_recipe,
        "suggestion_count": len(_as_list(feedback.get("action_recipes"))),
        "failure_reason": str(revision_result.get("failure_reason") or "").strip(),
    }

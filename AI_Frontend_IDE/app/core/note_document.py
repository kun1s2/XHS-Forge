"""Formal NoteDocument bridge layer.

This module is the single place where the workspace folds runtime state into
the canonical document protocol and, when a node needs a compact editing view,
projects the document into a normalized read-only layout snapshot.
"""

from copy import deepcopy
from typing import Any

from app.core.component_manifest import get_asset_support, get_component_entry, get_editable_targets, normalize_component_type
from app.agents.utils.fact_utils import FACT_FIELD_LABELS


def _label_fact_fields(fields: list[str]) -> list[str]:
    labels: list[str] = []
    for field in fields:
        field_key = str(field).strip()
        if not field_key:
            continue
        labels.append(FACT_FIELD_LABELS.get(field_key, field_key))
    return labels


def _extract_asset_urls(payload: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    if not isinstance(payload, dict):
        return urls
    image_url = payload.get("image_url")
    if isinstance(image_url, str) and image_url.strip():
        urls.append(image_url.strip())
    for item in payload.get("image_urls") or []:
        if isinstance(item, str) and item.strip():
            urls.append(item.strip())
    return urls


def _normalize_document_assets(
    image_assets: list[dict[str, Any]] | None,
    blocks: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    normalized_assets = []
    normalized_blocks = [block for block in (blocks or []) if isinstance(block, dict)]
    for asset in deepcopy(image_assets or []):
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        used_by_blocks = []
        for block in normalized_blocks:
            asset_refs = list(block.get("asset_refs") or [])
            props = block.get("props") or {}
            if not asset_refs:
                asset_refs = _extract_asset_urls(props)
            if asset["url"] in asset_refs:
                used_by_blocks.append(str(block.get("id") or ""))
        normalized_assets.append({
            "id": asset.get("id") or asset["url"],
            "url": asset["url"],
            "desc": asset.get("desc", ""),
            "source_type": asset.get("source_type", "unknown"),
            "query": asset.get("query"),
            "role": asset.get("role") or "supporting",
            "locked": bool(asset.get("locked", False)),
            "selection_state": asset.get("selection_state", "available"),
            "source_reason": asset.get("source_reason") or asset.get("desc", ""),
            "used_by_blocks": [block_id for block_id in used_by_blocks if block_id],
        })
    return normalized_assets


def build_note_document(
    *,
    document_view: dict[str, Any] | None = None,
    block_style_map: dict[str, Any] | None = None,
    image_assets: list[dict[str, Any]] | None = None,
    patch_tracks: dict[str, Any] | None = None,
    selected_element_id: str | None = None,
    active_panel: str | None = None,
    scenarios: list[str] | None = None,
    active_archetype: str | None = None,
    retrieved_knowledge: dict[str, Any] | None = None,
    planner_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = deepcopy(document_view or {})
    styles = deepcopy(block_style_map or {})
    assets = deepcopy(image_assets or [])
    tracks = deepcopy(patch_tracks or {})
    knowledge = deepcopy(retrieved_knowledge or {})
    blocks = []
    top_level_fact_bindings = []

    block_list = list(data.get("blocks") or [])
    for index, block in enumerate(block_list):
        block_id = str(block.get("id") or f"block_{index}")
        component_type = normalize_component_type(block.get("component_type")) or str(block.get("component_type") or "")
        props = deepcopy(data.get(block_id, {}) or {})
        block_style = deepcopy(styles.get(block_id, {}) or {})
        asset_refs = _extract_asset_urls(props)
        block_fact_bindings = []
        component_entry = get_component_entry(component_type) or {}
        editable_targets = get_editable_targets(component_type)

        paragraph_meta = props.get("paragraph_meta") or []
        for paragraph_index, meta in enumerate(paragraph_meta):
            if isinstance(meta, dict) and (meta.get("sources") or meta.get("hint")):
                fact_fields = [str(item) for item in (meta.get("fields") or []) if str(item).strip()]
                block_fact_bindings.append({
                    "field": f"paragraphs[{paragraph_index}]",
                    "fact_fields": fact_fields,
                    "fact_field_labels": _label_fact_fields(fact_fields),
                    "kind": meta.get("kind") or "default",
                    "sources": list(meta.get("sources") or []),
                    "hint": meta.get("hint"),
                })

        feature_meta = props.get("feature_meta") or []
        for feature_index, meta in enumerate(feature_meta):
            if isinstance(meta, dict) and (meta.get("sources") or meta.get("hint")):
                fact_fields = []
                if meta.get("field"):
                    fact_fields.append(str(meta.get("field")))
                for field_name in meta.get("fields") or []:
                    field_text = str(field_name).strip()
                    if field_text and field_text not in fact_fields:
                        fact_fields.append(field_text)
                block_fact_bindings.append({
                    "field": f"core_features[{feature_index}]",
                    "fact_fields": fact_fields,
                    "fact_field_labels": _label_fact_fields(fact_fields),
                    "kind": meta.get("kind") or "default",
                    "sources": list(meta.get("sources") or []),
                    "hint": meta.get("hint"),
                })

        blocks.append({
            "id": block_id,
            "type": component_type,
            "label": component_entry.get("label") or component_type,
            "semantic_role": component_entry.get("semantic_role") or "content",
            "content_brief": block.get("content_brief", ""),
            "props": props,
            "style": block_style,
            "asset_refs": asset_refs,
            "fact_bindings": block_fact_bindings,
            "editable_targets": editable_targets,
            "asset_support": get_asset_support(component_type),
            "fact_binding_support": bool(component_entry.get("fact_binding_support")),
            "order": index,
        })
        if block_fact_bindings:
            top_level_fact_bindings.append({"block_id": block_id, "bindings": block_fact_bindings})

    normalized_assets = _normalize_document_assets(assets, blocks)

    return {
        "document_meta": {
            "title": data.get("page_title") or "XHS-Forge Note",
            "active_archetype": active_archetype or "general",
            "scenarios": list(scenarios or [active_archetype or "general"]),
        },
        "theme": {
            "page_theme": deepcopy(data.get("page_theme") or {}),
            "global_vars": deepcopy(styles.get("global_vars") or {}),
        },
        "blocks": blocks,
        "assets": normalized_assets,
        "fact_bindings": top_level_fact_bindings,
        "provenance": {
            "fact_sources": deepcopy(knowledge.get("fact_sources") or []),
            "fact_conflicts": deepcopy(knowledge.get("fact_conflicts") or []),
            "confirmed_facts": deepcopy(knowledge.get("confirmed_facts") or {}),
            "fact_review_status": knowledge.get("fact_review_status") or "clear",
        },
        "ui_state": {
            "selected_element_id": selected_element_id,
            "active_panel": active_panel or "main",
            "patch_tracks": tracks,
        },
        "planner": deepcopy(planner_output or {}),
    }


def note_document_to_document_view(note_document: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    note_document = deepcopy(note_document or {})
    document_view: dict[str, Any] = {
        "page_title": ((note_document.get("document_meta") or {}).get("title") or "XHS-Forge Note"),
        "page_theme": deepcopy(((note_document.get("theme") or {}).get("page_theme") or {})),
        "blocks": [],
    }
    block_style_map: dict[str, Any] = {
        "global_vars": deepcopy(((note_document.get("theme") or {}).get("global_vars") or {})),
    }

    for block in note_document.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("id") or "")
        component_type = normalize_component_type(block.get("type")) or str(block.get("type") or "")
        if not block_id or not component_type:
            continue
        document_view["blocks"].append({
            "id": block_id,
            "component_type": component_type,
            "content_brief": block.get("content_brief", ""),
        })
        document_view[block_id] = deepcopy(block.get("props") or {})
        block_style_map[block_id] = deepcopy(block.get("style") or {})

    image_assets = []
    for asset in note_document.get("assets") or []:
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        image_assets.append({
            "url": asset.get("url"),
            "desc": asset.get("desc", ""),
            "source_type": asset.get("source_type"),
            "query": asset.get("query"),
            "locked": asset.get("locked", False),
            "selection_state": asset.get("selection_state"),
            "source_reason": asset.get("source_reason"),
        })
    return document_view, block_style_map, image_assets


def build_document_view_from_note_document(note_document: dict[str, Any] | None) -> dict[str, Any]:
    note_document = deepcopy(note_document or {})
    blocks: list[dict[str, Any]] = []
    for index, block in enumerate(note_document.get("blocks") or []):
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("id") or f"block_{index}")
        component_type = normalize_component_type(block.get("type")) or str(block.get("type") or "")
        if not component_type:
            continue
        blocks.append({
            "id": block_id,
            "component_type": component_type,
            "content_brief": block.get("content_brief", ""),
            "props": deepcopy(block.get("props") or {}),
            "style": deepcopy(block.get("style") or {}),
            "semantic_role": block.get("semantic_role") or "content",
            "editable_targets": deepcopy(block.get("editable_targets") or []),
            "asset_support": block.get("asset_support") or get_asset_support(component_type),
            "fact_binding_support": bool(block.get("fact_binding_support")),
        })

    return {
        "page_title": ((note_document.get("document_meta") or {}).get("title") or "XHS-Forge Note"),
        "page_theme": deepcopy(((note_document.get("theme") or {}).get("page_theme") or {})),
        "global_vars": deepcopy(((note_document.get("theme") or {}).get("global_vars") or {})),
        "blocks": blocks,
        "assets": deepcopy(note_document.get("assets") or []),
    }


def build_note_document_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    state = state or {}
    existing = deepcopy(state.get("note_document") or {})
    if isinstance(existing, dict) and existing.get("blocks") is not None:
        document_meta = existing.setdefault("document_meta", {})
        ui_state = existing.setdefault("ui_state", {})
        provenance = existing.setdefault("provenance", {})
        planner = existing.setdefault("planner", {})

        if state.get("active_archetype"):
            document_meta["active_archetype"] = state.get("active_archetype")
        if state.get("scenarios"):
            document_meta["scenarios"] = list(state.get("scenarios") or [])
        if state.get("selected_element_id") is not None:
            ui_state["selected_element_id"] = state.get("selected_element_id")
        if state.get("active_panel"):
            ui_state["active_panel"] = state.get("active_panel")
        if state.get("patch_tracks") is not None:
            ui_state["patch_tracks"] = deepcopy(state.get("patch_tracks") or {})
        if isinstance(state.get("retrieved_knowledge"), dict):
            knowledge = state.get("retrieved_knowledge") or {}
            provenance["fact_sources"] = deepcopy(knowledge.get("fact_sources") or provenance.get("fact_sources") or [])
            provenance["fact_conflicts"] = deepcopy(knowledge.get("fact_conflicts") or provenance.get("fact_conflicts") or [])
            provenance["confirmed_facts"] = deepcopy(knowledge.get("confirmed_facts") or provenance.get("confirmed_facts") or {})
            provenance["fact_review_status"] = knowledge.get("fact_review_status") or provenance.get("fact_review_status") or "clear"
        if state.get("planner_output") is not None:
            existing["planner"] = deepcopy(state.get("planner_output") or {})
        if state.get("image_assets") is not None:
            existing["assets"] = _normalize_document_assets(state.get("image_assets") or [], existing.get("blocks") or [])
        return existing

    return build_note_document(
        document_view=state.get("document_view"),
        block_style_map=state.get("block_style_map"),
        image_assets=state.get("image_assets"),
        patch_tracks=state.get("patch_tracks"),
        selected_element_id=state.get("selected_element_id"),
        active_panel=state.get("active_panel"),
        scenarios=state.get("scenarios"),
        active_archetype=state.get("active_archetype"),
        retrieved_knowledge=state.get("retrieved_knowledge"),
        planner_output=state.get("planner_output"),
    )


def build_document_view_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Project runtime state into the normalized document view."""
    return build_document_view_from_note_document(build_note_document_from_state(state))


def build_document_editing_context_from_state(
    state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Bridge runtime state into a compact document editing context."""
    note_document = build_note_document_from_state(state)
    document_view, block_style_map, image_assets = note_document_to_document_view(note_document)
    return note_document, document_view, block_style_map, image_assets


def update_note_document_block(
    note_document: dict[str, Any] | None,
    block_id: str,
    *,
    props: dict[str, Any] | None = None,
    style: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = deepcopy(note_document or {})
    blocks = list(document.get("blocks") or [])
    for block in blocks:
        if str(block.get("id") or "") != str(block_id):
            continue
        if props is not None:
            block["props"] = deepcopy(props)
        if style is not None:
            block["style"] = deepcopy(style)
        if metadata:
            for key, value in metadata.items():
                block[key] = deepcopy(value)
        break
    document["blocks"] = blocks
    return document


def update_note_document_theme(
    note_document: dict[str, Any] | None,
    *,
    page_theme: dict[str, Any] | None = None,
    global_vars: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = deepcopy(note_document or {})
    theme = document.setdefault("theme", {})
    if page_theme is not None:
        theme["page_theme"] = deepcopy(page_theme)
    if global_vars is not None:
        theme["global_vars"] = deepcopy(global_vars)
    return document


def update_note_document_title(note_document: dict[str, Any] | None, title: str) -> dict[str, Any]:
    document = deepcopy(note_document or {})
    meta = document.setdefault("document_meta", {})
    meta["title"] = title
    return document


def replace_note_document_blocks(note_document: dict[str, Any] | None, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    document = deepcopy(note_document or {})
    document["blocks"] = deepcopy(blocks)
    return document


def append_note_document_block(
    note_document: dict[str, Any] | None,
    block: dict[str, Any],
    *,
    props: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = deepcopy(note_document or {})
    blocks = list(document.get("blocks") or [])
    component_type = normalize_component_type(block.get("component_type")) or str(block.get("type") or block.get("component_type") or "")
    block_id = str(block.get("id") or "")
    component_entry = get_component_entry(component_type) or {}
    if not block_id or not component_type:
        return document
    blocks.append({
        "id": block_id,
        "type": component_type,
        "label": component_entry.get("label") or component_type,
        "semantic_role": component_entry.get("semantic_role") or "content",
        "content_brief": block.get("content_brief", ""),
        "props": deepcopy(props or {}),
        "style": {},
        "asset_refs": [],
        "fact_bindings": [],
        "editable_targets": get_editable_targets(component_type),
        "asset_support": get_asset_support(component_type),
        "fact_binding_support": bool(component_entry.get("fact_binding_support")),
        "order": len(blocks),
    })
    for index, item in enumerate(blocks):
        item["order"] = index
    document["blocks"] = blocks
    return document


def insert_note_document_block(
    note_document: dict[str, Any] | None,
    block: dict[str, Any],
    index: int,
    *,
    props: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = deepcopy(note_document or {})
    blocks = list(document.get("blocks") or [])
    component_type = normalize_component_type(block.get("component_type")) or str(block.get("type") or block.get("component_type") or "")
    block_id = str(block.get("id") or "")
    component_entry = get_component_entry(component_type) or {}
    if not block_id or not component_type:
        return document
    safe_index = min(max(0, index), len(blocks))
    blocks.insert(safe_index, {
        "id": block_id,
        "type": component_type,
        "label": component_entry.get("label") or component_type,
        "semantic_role": component_entry.get("semantic_role") or "content",
        "content_brief": block.get("content_brief", ""),
        "props": deepcopy(props or {}),
        "style": {},
        "asset_refs": [],
        "fact_bindings": [],
        "editable_targets": get_editable_targets(component_type),
        "asset_support": get_asset_support(component_type),
        "fact_binding_support": bool(component_entry.get("fact_binding_support")),
        "order": safe_index,
    })
    for new_index, item in enumerate(blocks):
        item["order"] = new_index
    document["blocks"] = blocks
    return document


def remove_note_document_block(note_document: dict[str, Any] | None, block_id: str) -> dict[str, Any]:
    document = deepcopy(note_document or {})
    blocks = [block for block in (document.get("blocks") or []) if str(block.get("id") or "") != str(block_id)]
    for index, block in enumerate(blocks):
        block["order"] = index
    document["blocks"] = blocks
    return document


def build_note_document_from_structure_patch(
    note_document: dict[str, Any] | None,
    *,
    page_title: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
    component_payloads: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = deepcopy(note_document or {})
    current_blocks = list(document.get("blocks") or [])
    current_by_id = {
        str(block.get("id") or ""): deepcopy(block)
        for block in current_blocks
        if isinstance(block, dict) and block.get("id")
    }
    component_payloads = deepcopy(component_payloads or {})

    next_blocks: list[dict[str, Any]] = []
    for order, block in enumerate(blocks or []):
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("id") or "")
        component_type = normalize_component_type(block.get("component_type")) or str(block.get("component_type") or "")
        if not block_id or not component_type:
            continue
        current_block = current_by_id.get(block_id, {})
        component_entry = get_component_entry(component_type) or {}
        next_blocks.append({
            "id": block_id,
            "type": component_type,
            "label": component_entry.get("label") or component_type,
            "semantic_role": component_entry.get("semantic_role") or current_block.get("semantic_role") or "content",
            "content_brief": block.get("content_brief", ""),
            "props": deepcopy(component_payloads.get(block_id) or current_block.get("props") or {}),
            "style": deepcopy(current_block.get("style") or {}),
            "asset_refs": deepcopy(current_block.get("asset_refs") or []),
            "fact_bindings": deepcopy(current_block.get("fact_bindings") or []),
            "editable_targets": deepcopy(current_block.get("editable_targets") or get_editable_targets(component_type)),
            "asset_support": current_block.get("asset_support") or get_asset_support(component_type),
            "fact_binding_support": bool(
                current_block.get("fact_binding_support")
                if current_block.get("fact_binding_support") is not None
                else component_entry.get("fact_binding_support")
            ),
            "order": order,
        })

    document["blocks"] = next_blocks
    if page_title is not None:
        meta = document.setdefault("document_meta", {})
        meta["title"] = page_title or "XHS-Forge Note"
    return document

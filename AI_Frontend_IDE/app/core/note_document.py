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


def _pick_grounding_sources(knowledge: dict[str, Any], preferred_scope: str | None = None, limit: int = 3) -> list[str]:
    sources = [item for item in (knowledge.get("fact_sources") or []) if isinstance(item, dict)]
    if preferred_scope:
        scoped = [
            str(item.get("title") or item.get("url") or "").strip()
            for item in sources
            if str(item.get("source_scope") or "").strip() == preferred_scope and str(item.get("title") or item.get("url") or "").strip()
        ]
        if scoped:
            return scoped[:limit]
    fallback = [
        str(item.get("title") or item.get("url") or "").strip()
        for item in sources
        if str(item.get("title") or item.get("url") or "").strip()
    ]
    return fallback[:limit]


def _build_retrieval_fact_bindings(
    *,
    block_type: str,
    props: dict[str, Any],
    knowledge: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(knowledge, dict) or not (knowledge.get("fact_sources") or knowledge.get("confirmed_facts")):
        return []

    bindings: list[dict[str, Any]] = []
    if block_type == "ProductSpecCard" and props.get("core_features"):
        bindings.append({
            "field": "core_features",
            "fact_fields": [str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()],
            "fact_field_labels": _label_fact_fields([str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()]),
            "kind": "retrieval_grounded",
            "sources": _pick_grounding_sources(knowledge, preferred_scope="official"),
            "hint": "该参数卡引用了本轮检索到的官方/高可信资料",
        })
    elif block_type == "StoryText" and props.get("paragraphs"):
        bindings.append({
            "field": "paragraphs[0]",
            "fact_fields": [str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()],
            "fact_field_labels": _label_fact_fields([str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()]),
            "kind": "retrieval_grounded",
            "sources": _pick_grounding_sources(knowledge, preferred_scope="review"),
            "hint": "该段正文引用了本轮检索证据或已确认事实",
        })
    elif block_type == "LocationBlock":
        bindings.append({
            "field": "poi_name",
            "fact_fields": [],
            "fact_field_labels": [],
            "kind": "retrieval_grounded",
            "sources": _pick_grounding_sources(knowledge, preferred_scope="official"),
            "hint": "该地点信息引用了本轮检索资料",
        })
    elif block_type == "RadarChartBlock" and props.get("scores"):
        bindings.append({
            "field": "scores",
            "fact_fields": [str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()],
            "fact_field_labels": _label_fact_fields([str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()]),
            "kind": "retrieval_grounded",
            "sources": _pick_grounding_sources(knowledge, preferred_scope="official"),
            "hint": "该评分概览由本轮检索证据支撑",
        })
    elif block_type == "VersusCard" and (props.get("proText") or props.get("conText")):
        bindings.append({
            "field": "comparison_copy",
            "fact_fields": [],
            "fact_field_labels": [],
            "kind": "retrieval_grounded",
            "sources": _pick_grounding_sources(knowledge, preferred_scope="review"),
            "hint": "该对比结论综合了本轮检索到的口碑/评价来源",
        })
    return [item for item in bindings if item.get("sources")]


def _apply_retrieval_grounding_to_document(note_document: dict[str, Any] | None, knowledge: dict[str, Any] | None) -> dict[str, Any]:
    document = deepcopy(note_document or {})
    safe_knowledge = knowledge if isinstance(knowledge, dict) else {}
    if not safe_knowledge:
        return document

    blocks = []
    top_level_fact_bindings = []
    for block in document.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        next_block = deepcopy(block)
        existing_bindings = [item for item in (next_block.get("fact_bindings") or []) if isinstance(item, dict)]
        derived_bindings = _build_retrieval_fact_bindings(
            block_type=str(next_block.get("type") or ""),
            props=deepcopy(next_block.get("props") or {}),
            knowledge=safe_knowledge,
        )
        merged_bindings = existing_bindings[:]
        existing_fields = {str(item.get("field") or "") for item in existing_bindings}
        for item in derived_bindings:
            if str(item.get("field") or "") not in existing_fields:
                merged_bindings.append(item)
        next_block["fact_bindings"] = merged_bindings
        blocks.append(next_block)
        if merged_bindings:
            top_level_fact_bindings.append({"block_id": str(next_block.get("id") or ""), "bindings": merged_bindings})

    document["blocks"] = blocks
    document["fact_bindings"] = top_level_fact_bindings
    return document


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

    document = {
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
    return _apply_retrieval_grounding_to_document(document, knowledge)


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


def build_note_document_layout(note_document: dict[str, Any] | None) -> dict[str, Any]:
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
        return _apply_retrieval_grounding_to_document(existing, state.get("retrieved_knowledge") or {})

    document = {
        "document_meta": {
            "title": "XHS-Forge Note",
            "active_archetype": state.get("active_archetype") or "general",
            "scenarios": list(state.get("scenarios") or [state.get("active_archetype") or "general"]),
        },
        "theme": {
            "page_theme": {},
            "global_vars": {},
        },
        "blocks": [],
        "assets": _normalize_document_assets(state.get("image_assets") or [], []),
        "fact_bindings": [],
        "provenance": {
            "fact_sources": deepcopy(((state.get("retrieved_knowledge") or {}) if isinstance(state.get("retrieved_knowledge"), dict) else {}).get("fact_sources") or []),
            "fact_conflicts": deepcopy(((state.get("retrieved_knowledge") or {}) if isinstance(state.get("retrieved_knowledge"), dict) else {}).get("fact_conflicts") or []),
            "confirmed_facts": deepcopy(((state.get("retrieved_knowledge") or {}) if isinstance(state.get("retrieved_knowledge"), dict) else {}).get("confirmed_facts") or {}),
            "fact_review_status": (((state.get("retrieved_knowledge") or {}) if isinstance(state.get("retrieved_knowledge"), dict) else {}).get("fact_review_status") or "clear"),
        },
        "ui_state": {
            "selected_element_id": state.get("selected_element_id"),
            "active_panel": state.get("active_panel") or "main",
            "patch_tracks": deepcopy(state.get("patch_tracks") or {}),
        },
        "planner": deepcopy(state.get("planner_output") or {}),
    }
    return _apply_retrieval_grounding_to_document(document, state.get("retrieved_knowledge") or {})


def build_note_document_layout_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Project runtime state into the normalized document layout."""
    return build_note_document_layout(build_note_document_from_state(state))


def build_note_document_editing_context(
    state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Build the compact editing context derived from the formal NoteDocument."""
    note_document = build_note_document_from_state(state)
    document_view, block_style_map, image_assets = note_document_to_document_view(note_document)
    return note_document, document_view, block_style_map, image_assets


def build_document_view_from_note_document(note_document: dict[str, Any] | None) -> dict[str, Any]:
    """Backward-compatible wrapper for tests; runtime code should use build_note_document_layout."""
    return build_note_document_layout(note_document)


def build_document_view_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Backward-compatible wrapper for tests; runtime code should use build_note_document_layout_from_state."""
    return build_note_document_layout_from_state(state)


def build_document_editing_context_from_state(
    state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Backward-compatible wrapper for tests; runtime code should use build_note_document_editing_context."""
    return build_note_document_editing_context(state)


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

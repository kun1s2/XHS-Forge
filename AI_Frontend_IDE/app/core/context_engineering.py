from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.component_manifest import get_component_semantic_role, get_editable_targets


def build_policy_summary(planner_policy: dict[str, Any] | None) -> dict[str, Any]:
    safe_policy = planner_policy if isinstance(planner_policy, dict) else {}
    tone_policy = safe_policy.get("tone_policy", {}) if isinstance(safe_policy.get("tone_policy"), dict) else {}
    layout_policy = safe_policy.get("layout_policy", {}) if isinstance(safe_policy.get("layout_policy"), dict) else {}
    theme_policy = safe_policy.get("theme_policy", {}) if isinstance(safe_policy.get("theme_policy"), dict) else {}
    asset_policy = safe_policy.get("asset_policy", {}) if isinstance(safe_policy.get("asset_policy"), dict) else {}
    fact_policy = safe_policy.get("fact_policy", {}) if isinstance(safe_policy.get("fact_policy"), dict) else {}
    return {
        "tone": {
            "style": tone_policy.get("style") or tone_policy.get("tone") or tone_policy.get("bias") or "",
            "intensity": tone_policy.get("intensity") or tone_policy.get("strength") or "",
        },
        "layout": {
            "preferred_block_intents": list(layout_policy.get("preferred_block_intents") or [])[:6],
            "interaction_bias": layout_policy.get("interaction_bias") or "",
        },
        "theme": {
            "preset": theme_policy.get("preset") or "",
            "interaction_level": theme_policy.get("interaction_level") or theme_policy.get("interaction_bias") or "",
        },
        "assets": {
            "mode": asset_policy.get("mode") or "",
            "allowed_tools": list(asset_policy.get("allowed_tools") or [])[:4],
        },
        "facts": {
            "prefer_confirmed": bool(fact_policy.get("prefer_confirmed_facts")),
            "cautious_fallback": bool(fact_policy.get("fallback_to_cautious_copy")),
        },
    }


def build_asset_summary(image_assets: list[dict[str, Any]] | None, *, limit: int = 3) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for asset in image_assets or []:
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        summary.append(
            {
                "role": str(asset.get("role") or "supporting"),
                "desc": str(asset.get("desc") or asset.get("source_reason") or "素材图")[:80],
                "source_type": str(asset.get("source_type") or "unknown"),
            }
        )
        if len(summary) >= limit:
            break
    return summary


def build_fact_summary(retrieved_knowledge: dict[str, Any] | None, image_assets: list[dict[str, Any]] | None) -> dict[str, Any]:
    knowledge = retrieved_knowledge if isinstance(retrieved_knowledge, dict) else {}
    attrs = knowledge.get("core_attributes") if isinstance(knowledge.get("core_attributes"), dict) else {}
    confirmed = knowledge.get("confirmed_facts") if isinstance(knowledge.get("confirmed_facts"), dict) else {}
    conflict_list = knowledge.get("fact_conflicts") if isinstance(knowledge.get("fact_conflicts"), list) else []
    return {
        "entity": knowledge.get("entity_name") or "",
        "key_selling_points": list(knowledge.get("key_selling_points") or [])[:4],
        "known_issues": list(knowledge.get("known_issues") or [])[:4],
        "core_attributes": dict(list(attrs.items())[:6]),
        "confirmed_facts": dict(list(confirmed.items())[:6]),
        "conflict_count": len(conflict_list),
        "image_count": len([asset for asset in (image_assets or []) if isinstance(asset, dict) and asset.get("url")]),
    }


def count_fact_summary_entries(fact_summary: dict[str, Any] | None) -> int:
    summary = fact_summary if isinstance(fact_summary, dict) else {}
    count = 0
    if summary.get("entity"):
        count += 1
    count += len(summary.get("key_selling_points") or [])
    count += len(summary.get("known_issues") or [])
    count += len(summary.get("core_attributes") or {})
    count += len(summary.get("confirmed_facts") or {})
    if summary.get("conflict_count"):
        count += 1
    return count


def build_retrieval_evidence_slice(
    retrieved_knowledge: dict[str, Any] | None,
    *,
    semantic_role: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    knowledge = retrieved_knowledge if isinstance(retrieved_knowledge, dict) else {}
    fact_sources = [item for item in (knowledge.get("fact_sources") or []) if isinstance(item, dict)]
    if not fact_sources:
        return []

    preferred_scopes: list[str]
    if semantic_role in {"evidence_summary", "score_overview", "location_info"}:
        preferred_scopes = ["official", "fact"]
    elif semantic_role in {"comparison", "interactive_opinion", "narrative_text"}:
        preferred_scopes = ["review", "community", "comparison"]
    else:
        preferred_scopes = ["official", "review"]

    ranked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for scope in preferred_scopes + ["official", "review", "community", "comparison"]:
        for item in fact_sources:
            key = str(item.get("url") or item.get("title") or "").strip()
            if not key or key in seen:
                continue
            item_scope = str(item.get("source_scope") or "").strip()
            if item_scope != scope:
                continue
            seen.add(key)
            ranked.append(
                {
                    "title": str(item.get("title") or key),
                    "scope": item_scope or "unknown",
                    "snippet": str(item.get("snippet") or "")[:160],
                }
            )
            if len(ranked) >= limit:
                return ranked
    for item in fact_sources:
        key = str(item.get("url") or item.get("title") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ranked.append(
            {
                "title": str(item.get("title") or key),
                "scope": str(item.get("source_scope") or "unknown"),
                "snippet": str(item.get("snippet") or "")[:160],
            }
        )
        if len(ranked) >= limit:
            break
    return ranked


def build_document_summary(note_document: dict[str, Any] | None) -> dict[str, Any]:
    document = note_document if isinstance(note_document, dict) else {}
    blocks = [block for block in (document.get("blocks") or []) if isinstance(block, dict)]
    return {
        "title": str((document.get("document_meta") or {}).get("title") or "未设置"),
        "block_count": len(blocks),
        "asset_count": len([asset for asset in (document.get("assets") or []) if isinstance(asset, dict)]),
        "theme_preset": str((document.get("theme") or {}).get("preset") or ""),
        "blocks": [
            {
                "id": str(block.get("id") or ""),
                "type": str(block.get("type") or block.get("component_type") or ""),
                "semantic_role": str(block.get("semantic_role") or get_component_semantic_role(str(block.get("type") or block.get("component_type") or "")) or ""),
                "editable_targets": list(block.get("editable_targets") or get_editable_targets(str(block.get("type") or block.get("component_type") or "")) or []),
                "content_brief": str(block.get("content_brief") or "")[:80],
            }
            for block in blocks[:8]
        ],
    }


def build_selection_context(
    *,
    note_document: dict[str, Any] | None,
    document_view: dict[str, Any] | None,
    block_style_map: dict[str, Any] | None,
    selected_element_id: str | None,
) -> dict[str, Any]:
    safe_document = note_document if isinstance(note_document, dict) else {}
    safe_document_view = document_view if isinstance(document_view, dict) else {}
    safe_style_map = block_style_map if isinstance(block_style_map, dict) else {}
    target_id = str(selected_element_id or "").strip()
    if not target_id:
        return {}

    selected_block = next(
        (deepcopy(block) for block in (safe_document.get("blocks") or []) if isinstance(block, dict) and str(block.get("id") or "") == target_id),
        {},
    )
    selected_props = deepcopy(safe_document_view.get(target_id) or {})
    selected_style = deepcopy(safe_style_map.get(target_id) or {})
    component_type = str(selected_block.get("type") or selected_block.get("component_type") or "")
    return {
        "id": target_id,
        "type": component_type,
        "semantic_role": str(selected_block.get("semantic_role") or get_component_semantic_role(component_type) or ""),
        "editable_targets": list(selected_block.get("editable_targets") or get_editable_targets(component_type) or []),
        "content_brief": str(selected_block.get("content_brief") or ""),
        "props": selected_props,
        "style": selected_style,
        "fact_bindings": deepcopy(selected_block.get("fact_bindings") or []),
    }

from __future__ import annotations

from copy import deepcopy
from typing import Any

from langchain_core.messages import HumanMessage

from app.agents.services.component_builder import build_component_fallback, enforce_component_contract
from app.agents.utils.entity_utils import (
    is_generic_entity_name,
    mentions_other_specific_entity,
    normalize_entity_name,
)
from app.core.component_manifest import (
    filter_payload_for_component,
    get_asset_support,
    get_component_entry,
    get_component_semantic_role,
    get_editable_targets,
    resolve_component_for_block_intent,
    supports_fact_binding,
)
from app.core.note_document import update_note_document_cover_preference
from app.core.query_heuristics import wants_image_search
from app.core.request_semantics import latest_user_text_from_state


PLACEHOLDER_TEXTS = {
    "TitleBlock",
    "StoryText",
    "等待封面图片接入...",
}

RISK_TOKENS = ("风险", "代价", "不适合", "边界", "妥协", "不足", "短板")
COMPARISON_TOKENS = ("优点", "缺点", "优缺点", "路线", "适合", "不适合", "代价", "取舍")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _latest_user_query(state: dict[str, Any]) -> str:
    latest = latest_user_text_from_state(state)
    if latest:
        return latest
    for msg in reversed(_as_list(state.get("main_messages") or state.get("messages"))):
        if not isinstance(msg, HumanMessage):
            continue
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            text = "".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
        else:
            text = str(content or "")
        text = text.strip()
        if text:
            return text
    return ""


def _entity_anchor(state: dict[str, Any]) -> str:
    retrieved_knowledge = _as_dict(state.get("retrieved_knowledge"))
    note_document = _as_dict(state.get("note_document"))
    document_meta = _as_dict(note_document.get("document_meta"))
    for candidate in (
        str(retrieved_knowledge.get("entity_name") or "").strip(),
        str(document_meta.get("title") or "").strip(),
        normalize_entity_name(_latest_user_query(state)),
    ):
        if candidate and not is_generic_entity_name(candidate):
            return candidate
    return ""


def _candidate_asset_urls(state: dict[str, Any], note_document: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for asset in [*_as_list(note_document.get("assets")), *_as_list(state.get("image_assets"))]:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("selection_state") or "").strip().lower() == "excluded":
            continue
        url = str(asset.get("url") or "").strip()
        if not url:
            continue
        if url not in urls:
            urls.append(url)
    return urls


def _candidate_assets(state: dict[str, Any], note_document: dict[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for asset in [*_as_list(note_document.get("assets")), *_as_list(state.get("image_assets"))]:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("selection_state") or "").strip().lower() == "excluded":
            continue
        if not str(asset.get("url") or "").strip():
            continue
        assets.append(asset)
    return assets


def _asset_matches_entity(asset: dict[str, Any], entity_anchor: str) -> bool:
    normalized_entity = normalize_entity_name(entity_anchor)
    if not normalized_entity:
        return True
    haystack = " ".join(
        str(asset.get(key) or "").strip()
        for key in ("url", "desc", "query", "source_reason")
    ).lower()
    if not haystack:
        return False
    lowered_entity = normalized_entity.lower()
    if lowered_entity in haystack:
        return True
    entity_tokens = [token.strip().lower() for token in normalized_entity.split() if token.strip()]
    if len(entity_tokens) >= 2:
        matched = sum(1 for token in entity_tokens if token in haystack)
        return matched >= 2
    return entity_tokens[0] in haystack if entity_tokens else False


def _required_intents(state: dict[str, Any], note_document: dict[str, Any]) -> list[str]:
    planner_output = _as_dict(state.get("planner_output"))
    required = ["heading", "narrative_text", "fact_list", "comparison", "risk_boundary"]
    explicit_required = [
        str(item.get("intent_type") or "").strip()
        for item in _as_list(planner_output.get("block_intents"))
        if (
            isinstance(item, dict)
            and str(item.get("intent_type") or "").strip()
            and bool(item.get("required"))
        )
    ]
    for intent in explicit_required:
        if intent not in required:
            required.append(intent)
    query = _latest_user_query(state)
    intent_decision = _as_dict(state.get("intent_decision"))
    needs_assets = bool(intent_decision.get("needs_assets"))
    if (
        needs_assets
        or wants_image_search(query)
        or _candidate_asset_urls(state, note_document)
        or any(str(block.get("semantic_role") or "") == "hero_media" for block in _as_list(note_document.get("blocks")))
    ):
        if "hero_media" not in required:
            required.insert(0, "hero_media")
    deduped: list[str] = []
    seen: set[str] = set()
    for intent in required:
        if intent and intent not in seen:
            seen.add(intent)
            deduped.append(intent)
    return deduped


def _block_text(block: dict[str, Any]) -> str:
    props = _as_dict(block.get("props"))
    component_type = str(block.get("type") or "").strip()
    parts: list[str] = []
    if component_type == "TitleBlock":
        parts.extend([str(props.get("title") or "").strip(), str(props.get("subtitle") or "").strip()])
    elif component_type == "StoryText":
        parts.extend(str(item).strip() for item in _as_list(props.get("paragraphs")) if str(item).strip())
    elif component_type == "ProductSpecCard":
        parts.extend(str(item).strip() for item in _as_list(props.get("core_features")) if str(item).strip())
        for item in _as_list(props.get("spec_items")):
            if isinstance(item, dict):
                parts.extend(
                    str(item.get(key) or "").strip()
                    for key in ("label", "value", "decision_impact")
                    if str(item.get(key) or "").strip()
                )
    elif component_type == "VersusCard":
        parts.extend(
            str(props.get(key) or "").strip()
            for key in ("title", "decision_hint", "risk_note", "proText", "conText")
            if str(props.get(key) or "").strip()
        )
        for side in ("pros", "cons"):
            side_payload = _as_dict(props.get(side))
            parts.extend(
                str(side_payload.get(key) or "").strip()
                for key in ("summary", "details", "fit_for")
                if str(side_payload.get(key) or "").strip()
            )
    elif component_type == "PollBlock":
        parts.extend(
            str(props.get(key) or "").strip()
            for key in ("question", "option_a", "option_b")
            if str(props.get(key) or "").strip()
        )
    elif component_type == "CoverSwiper":
        parts.extend(
            str(props.get(key) or "").strip()
            for key in ("title", "description", "deck_summary")
            if str(props.get(key) or "").strip()
        )
    return " ".join(part for part in parts if part)


def _block_covers_intents(block: dict[str, Any]) -> set[str]:
    component_type = str(block.get("type") or "").strip()
    role = str(block.get("semantic_role") or get_component_semantic_role(component_type) or "").strip()
    covered: set[str] = set()
    if role == "heading":
        covered.add("heading")
    if role == "hero_media":
        covered.add("hero_media")
    if role == "narrative_text":
        covered.update({"narrative_text", "decision_summary"})
    if role == "score_overview":
        covered.add("decision_summary")
    if role == "evidence_summary":
        covered.add("fact_list")
    if role == "comparison" or component_type == "VersusCard":
        covered.update({"comparison", "risk_boundary"})
    text = _block_text(block)
    if any(token in text for token in RISK_TOKENS):
        covered.add("risk_boundary")
    return covered


def _has_meaningful_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text in PLACEHOLDER_TEXTS:
        return False
    return len(text) >= 4


def _block_specific_quality_issues(block: dict[str, Any]) -> list[str]:
    component_type = str(block.get("type") or "").strip()
    props = _as_dict(block.get("props"))
    issues: list[str] = []
    if component_type == "CoverSwiper":
        image_urls = [str(url).strip() for url in _as_list(props.get("image_urls")) if str(url).strip()]
        if not image_urls:
            issues.append("首屏图片没有真实绑定到页面。")
    elif component_type == "ProductSpecCard":
        feature_count = len([item for item in _as_list(props.get("core_features")) if _has_meaningful_text(item)])
        spec_count = len(
            [
                item for item in _as_list(props.get("spec_items"))
                if isinstance(item, dict) and (_has_meaningful_text(item.get("label")) or _has_meaningful_text(item.get("value")))
            ]
        )
        if feature_count + spec_count < 1:
            issues.append("参数/事实区块内容不足，无法支撑购买判断。")
    elif component_type == "VersusCard":
        pros = _as_dict(props.get("pros"))
        cons = _as_dict(props.get("cons"))
        comparison_text = " ".join(
            [
                str(props.get("title") or "").strip(),
                str(props.get("decision_hint") or "").strip(),
                str(props.get("risk_note") or "").strip(),
                str(pros.get("summary") or "").strip(),
                str(pros.get("details") or "").strip(),
                str(pros.get("fit_for") or "").strip(),
                str(cons.get("summary") or "").strip(),
                str(cons.get("details") or "").strip(),
                str(cons.get("fit_for") or "").strip(),
            ]
        )
        if not (_has_meaningful_text(pros.get("summary")) and _has_meaningful_text(cons.get("summary"))):
            issues.append("优缺点对比区块缺少明确的正反判断。")
        if not any(token in comparison_text for token in COMPARISON_TOKENS):
            issues.append("对比区块没有形成真正的取舍或路线表达。")
    elif component_type == "StoryText":
        paragraphs = [str(item).strip() for item in _as_list(props.get("paragraphs")) if _has_meaningful_text(item)]
        if not paragraphs:
            issues.append("正文区块没有形成有效叙述。")
    return issues


def _existing_intent_coverage(note_document: dict[str, Any]) -> set[str]:
    coverage: set[str] = set()
    for block in _as_list(note_document.get("blocks")):
        if isinstance(block, dict):
            coverage.update(_block_covers_intents(block))
    return coverage


def _next_block_id(note_document: dict[str, Any], component_type: str) -> str:
    prefix_map = {
        "CoverSwiper": "cover",
        "TitleBlock": "title",
        "StoryText": "story",
        "ProductSpecCard": "spec",
        "VersusCard": "versus",
        "RadarChartBlock": "radar",
        "PollBlock": "poll",
    }
    prefix = prefix_map.get(component_type, component_type.replace("Block", "").replace("Card", "").lower() or "block")
    existing = {
        str(item.get("id") or "").strip()
        for item in _as_list(note_document.get("blocks"))
        if isinstance(item, dict)
    }
    serial = len(existing) + 1
    block_id = f"{prefix}_{serial}"
    while block_id in existing:
        serial += 1
        block_id = f"{prefix}_{serial}"
    return block_id


def _infer_block_intent(block: dict[str, Any]) -> str:
    component_type = str(block.get("type") or "").strip()
    role = str(block.get("semantic_role") or get_component_semantic_role(component_type) or "").strip()
    if role == "hero_media":
        return "hero_media"
    if role == "heading":
        return "heading"
    if role in {"narrative_text", "score_overview"} or component_type == "StoryText":
        return "narrative_text"
    if role == "evidence_summary" or component_type == "ProductSpecCard":
        return "fact_list"
    if role == "comparison" or component_type == "VersusCard":
        return "comparison"
    return "narrative_text"


def _repair_content_quality_blocks(note_document: dict[str, Any], state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    entity_anchor = _entity_anchor({**state, "note_document": note_document})
    if not entity_anchor or is_generic_entity_name(entity_anchor):
        return deepcopy(note_document), []

    document = deepcopy(note_document)
    blocks = list(_as_list(document.get("blocks")))
    changed_blocks: list[dict[str, Any]] = []
    for index, raw_block in enumerate(blocks):
        if not isinstance(raw_block, dict):
            continue
        text = _block_text(raw_block)
        has_placeholder = any(token in text for token in PLACEHOLDER_TEXTS)
        has_foreign_entity = bool(text) and mentions_other_specific_entity(text, entity_anchor)
        if not has_placeholder and not has_foreign_entity:
            continue
        replacement = _build_fallback_block(_infer_block_intent(raw_block), state, document)
        replacement["id"] = str(raw_block.get("id") or replacement.get("id") or "")
        replacement["order"] = raw_block.get("order", replacement.get("order", index))
        if isinstance(raw_block.get("style"), dict) and raw_block.get("style"):
            replacement["style"] = deepcopy(raw_block.get("style"))
        blocks[index] = replacement
        changed_blocks.append(
            {
                "id": str(replacement.get("id") or ""),
                "type": str(replacement.get("type") or ""),
                "changed_fields": ["props", "content_brief", "entity_repair"],
            }
        )
    document["blocks"] = blocks
    return document, changed_blocks


def _build_fallback_block(intent_type: str, state: dict[str, Any], note_document: dict[str, Any]) -> dict[str, Any]:
    query = _latest_user_query(state)
    scenario_scores = _as_dict(state.get("scenario_scores"))
    component_type = resolve_component_for_block_intent(
        intent_type,
        has_images=bool(_candidate_asset_urls(state, note_document)),
        scenario_scores=scenario_scores,
    )
    block_id = _next_block_id(note_document, component_type)
    intent_labels = {
        "hero_media": "首屏封面",
        "heading": "标题结论",
        "narrative_text": "正文判断",
        "fact_list": "关键参数",
        "decision_summary": "判断总结",
        "comparison": "优缺点对比",
        "risk_boundary": "风险边界",
    }
    content_brief = intent_labels.get(intent_type, intent_type)
    payload = build_component_fallback(
        comp_type=component_type,
        comp_id=block_id,
        content_brief=content_brief,
        user_query=query,
        retrieved_knowledge=_as_dict(state.get("retrieved_knowledge")),
        image_assets=_as_list(note_document.get("assets")) or _as_list(state.get("image_assets")),
    )
    payload = enforce_component_contract(
        component_type,
        filter_payload_for_component(component_type, payload),
        payload,
    )
    return {
        "id": block_id,
        "type": component_type,
        "label": str((get_component_entry(component_type) or {}).get("label") or component_type),
        "semantic_role": get_component_semantic_role(component_type) or "content",
        "content_brief": content_brief,
        "props": payload,
        "style": {},
        "asset_refs": [item for item in _as_list(payload.get("image_urls")) if isinstance(item, str)]
        + ([str(payload.get("image_url"))] if str(payload.get("image_url") or "").strip() else []),
        "fact_bindings": [],
        "editable_targets": get_editable_targets(component_type),
        "asset_support": get_asset_support(component_type),
        "fact_binding_support": supports_fact_binding(component_type),
        "order": len(_as_list(note_document.get("blocks"))),
    }


def _ensure_cover_binding(note_document: dict[str, Any], state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    document = deepcopy(note_document)
    changed_blocks: list[dict[str, Any]] = []
    asset_urls = _candidate_asset_urls(state, document)
    if not asset_urls:
        return document, changed_blocks
    entity_anchor = _entity_anchor({**state, "note_document": document})
    candidate_assets = _candidate_assets(state, document)
    entity_matched_assets = [
        asset for asset in candidate_assets
        if _asset_matches_entity(asset, entity_anchor)
    ]
    if entity_matched_assets:
        asset_urls = [str(asset.get("url") or "").strip() for asset in entity_matched_assets if str(asset.get("url") or "").strip()]
    asset_urls = list(dict.fromkeys([url for url in asset_urls if url]))

    document = update_note_document_cover_preference(document, asset_urls[0])
    blocks = list(_as_list(document.get("blocks")))
    hero_index = next(
        (
            idx
            for idx, block in enumerate(blocks)
            if isinstance(block, dict)
            and str(block.get("semantic_role") or get_component_semantic_role(str(block.get("type") or "")) or "").strip() == "hero_media"
        ),
        None,
    )
    if hero_index is None:
        hero_block = _build_fallback_block("hero_media", state, document)
        hero_block["props"]["image_urls"] = asset_urls[:5]
        hero_block["asset_refs"] = asset_urls[:5]
        blocks.insert(0, hero_block)
        document["blocks"] = blocks
        changed_blocks.append({"id": hero_block["id"], "type": hero_block["type"], "changed_fields": ["added", "props", "asset_refs"]})
        return document, changed_blocks

    block = deepcopy(blocks[hero_index])
    props = _as_dict(block.get("props"))
    image_urls = [str(url).strip() for url in _as_list(props.get("image_urls")) if str(url).strip()]
    single_url = str(props.get("image_url") or "").strip()
    if single_url:
        image_urls.append(single_url)
    has_cover = bool(image_urls)
    has_entity_match = True
    if has_cover and entity_anchor:
        asset_lookup = {
            str(asset.get("url") or "").strip(): asset
            for asset in candidate_assets
            if str(asset.get("url") or "").strip()
        }
        has_entity_match = any(
            _asset_matches_entity(asset_lookup.get(url) or {"url": url}, entity_anchor)
            for url in image_urls
        )
    if has_cover and has_entity_match:
        return document, changed_blocks
    if str(block.get("type") or "") == "WeatherPolaroid":
        props["image_url"] = asset_urls[0]
        block["asset_refs"] = [asset_urls[0]]
    else:
        props["image_urls"] = asset_urls[:5]
        block["asset_refs"] = asset_urls[:5]
    block["props"] = props
    blocks[hero_index] = block
    document["blocks"] = blocks
    changed_blocks.append({"id": str(block.get("id") or ""), "type": str(block.get("type") or ""), "changed_fields": ["props", "asset_refs"]})
    return document, changed_blocks


def apply_artifact_quality_fixes(state: dict[str, Any]) -> dict[str, Any]:
    note_document = deepcopy(_as_dict(state.get("note_document")))
    if not note_document:
        return {
            "note_document": note_document,
            "artifact_quality": {"passed": False, "issues": ["当前没有可验证的页面成品。"], "missing_intents": [], "failure_reason": "artifact_quality_missing_document"},
            "autofix_changed_blocks": [],
        }

    changed_blocks: list[dict[str, Any]] = []
    entity_anchor = _entity_anchor({**state, "note_document": note_document})
    document_meta = _as_dict(note_document.get("document_meta"))
    title = str(document_meta.get("title") or "").strip()
    if entity_anchor and (not title or title == "XHS-Forge Note" or mentions_other_specific_entity(title, entity_anchor)):
        document_meta["title"] = f"{entity_anchor} 持续笔记"
        note_document["document_meta"] = document_meta
    note_document, repaired_blocks = _repair_content_quality_blocks(note_document, state)
    changed_blocks.extend(repaired_blocks)
    required_intents = _required_intents(state, note_document)
    if "hero_media" in required_intents:
        note_document, cover_changes = _ensure_cover_binding(note_document, state)
        changed_blocks.extend(cover_changes)

    coverage = _existing_intent_coverage(note_document)
    missing_intents = [intent for intent in required_intents if intent not in coverage]
    auto_fillable = [
        intent
        for intent in missing_intents
        if intent in {"heading", "narrative_text", "fact_list", "comparison", "risk_boundary"}
    ]
    for intent in auto_fillable:
        block = _build_fallback_block(intent, state, note_document)
        blocks = list(_as_list(note_document.get("blocks")))
        block["order"] = len(blocks)
        blocks.append(block)
        note_document["blocks"] = blocks
        changed_blocks.append({"id": block["id"], "type": block["type"], "changed_fields": ["added", "props"]})
    coverage = _existing_intent_coverage(note_document)
    missing_intents = [intent for intent in required_intents if intent not in coverage]

    issues: list[str] = []
    entity_anchor = _entity_anchor({**state, "note_document": note_document})
    title = str(_as_dict(note_document.get("document_meta")).get("title") or "").strip()
    visible_text = " ".join(_block_text(block) for block in _as_list(note_document.get("blocks")) if isinstance(block, dict))
    validated_entity = bool(entity_anchor and (entity_anchor in title or entity_anchor in visible_text))
    if entity_anchor and not validated_entity:
        issues.append(f"页面没有明确围绕「{entity_anchor}」展开。")

    for block in _as_list(note_document.get("blocks")):
        if not isinstance(block, dict):
            continue
        text = _block_text(block)
        if any(token in text for token in PLACEHOLDER_TEXTS):
            issues.append("页面仍包含占位文案，生成质量不达标。")
            break
        if text and entity_anchor and mentions_other_specific_entity(text, entity_anchor):
            issues.append("页面仍包含与当前目标不相关的实体或机型。")
            break

    component_issues: list[str] = []
    for block in _as_list(note_document.get("blocks")):
        if not isinstance(block, dict):
            continue
        component_issues.extend(_block_specific_quality_issues(block))
    issues.extend(component_issues)

    hero_required = "hero_media" in required_intents
    validated_images = False
    if hero_required:
        candidate_assets = _candidate_assets(state, note_document)
        candidate_by_url = {
            str(asset.get("url") or "").strip(): asset
            for asset in candidate_assets
            if str(asset.get("url") or "").strip()
        }
        hero_blocks = [
            block for block in _as_list(note_document.get("blocks"))
            if isinstance(block, dict)
            and str(block.get("semantic_role") or get_component_semantic_role(str(block.get("type") or "")) or "").strip() == "hero_media"
        ]
        if not hero_blocks:
            issues.append("页面缺少首屏主视觉。")
        else:
            hero_ok = False
            hero_entity_ok = False
            for block in hero_blocks:
                props = _as_dict(block.get("props"))
                image_urls = [str(url).strip() for url in _as_list(props.get("image_urls")) if str(url).strip()]
                single_url = str(props.get("image_url") or "").strip()
                if single_url:
                    image_urls.append(single_url)
                if image_urls:
                    hero_ok = True
                    if not entity_anchor:
                        hero_entity_ok = True
                    else:
                        for image_url in image_urls:
                            asset = candidate_by_url.get(image_url) or {"url": image_url}
                            if _asset_matches_entity(asset, entity_anchor):
                                hero_entity_ok = True
                                break
                if hero_ok and hero_entity_ok:
                    break
            if not hero_ok:
                issues.append("首屏图片没有真实绑定到页面。")
            elif not hero_entity_ok:
                issues.append("首屏图片与当前笔记实体不匹配。")
            validated_images = hero_ok and hero_entity_ok

    if "fact_list" in required_intents and "fact_list" not in coverage:
        issues.append("页面缺少关键参数/事实整理区块。")
    if "comparison" in required_intents and "comparison" not in coverage:
        issues.append("页面缺少优缺点或路线对比区块。")
    if "risk_boundary" in required_intents and "risk_boundary" not in coverage:
        issues.append("页面缺少明确的风险或代价边界。")

    passed = not issues and not missing_intents
    failure_reason = ""
    if not passed:
        failure_reason = "artifact_quality_failed:" + "；".join(issues or [f"missing={','.join(missing_intents)}"])
    return {
        "note_document": note_document,
        "artifact_quality": {
            "passed": passed,
            "issues": issues,
            "missing_intents": missing_intents,
            "required_intents": required_intents,
            "entity_anchor": entity_anchor,
            "validated_entity": validated_entity,
            "validated_images": validated_images if hero_required else True,
            "failure_reason": failure_reason,
            "autofix_applied": bool(changed_blocks),
        },
        "autofix_changed_blocks": changed_blocks,
    }


__all__ = ["apply_artifact_quality_fixes"]


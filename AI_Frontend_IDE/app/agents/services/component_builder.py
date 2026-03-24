"""契约优先的组件构建节点。

这个节点保留单工兵式生成路径，但把“真正负责治理输出”的工作交给外围
contract 层：组件归一化、字段过滤、能力提示、fallback 和 trace 都在这里
完成，工兵模型只负责填充一个狭窄、结构化的简报。
"""

import json
import asyncio
import random
import re
from copy import deepcopy
from typing import Any, List
from app.core.llm_factory import create_llm
from app.agents.utils.entity_utils import normalize_entity_name
from app.agents.utils.fact_utils import (
    build_conflict_safe_notes,
    build_fact_grounding_context,
    summarize_confirmed_attributes,
)
from app.agents.state import ComponentTaskState
from app.core.config import settings
from app.core.context_engineering import (
    build_asset_summary,
    build_fact_summary,
    build_policy_summary,
    build_retrieval_evidence_slice,
    count_fact_summary_entries,
)
from app.core.schema import ComponentBuilderOutput
from app.core.component_manifest import (
    filter_payload_for_component,
    get_asset_support,
    get_component_label,
    get_component_semantic_role,
    get_editable_targets,
    get_optional_props,
    get_quick_actions,
    get_required_props,
    get_theme_slots,
    normalize_component_type,
    supports_fact_binding,
)
from app.core.note_document import build_note_document_from_state
from app.core.prompt_engineering import build_prompt_snapshot, render_string_prompt

# 限制并发工兵生成任务数量，避免高峰期把外部模型打爆。
_github_limiter = asyncio.Semaphore(10)

_llm_instance = None
def get_builder_llm():
    """懒加载 builder 使用的主文本模型。"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.3
        )
    return _llm_instance


VERIFIED_FEATURE_PREFIX = "__verified__"


def _split_readable_points(value: Any, *, limit: int = 3) -> list[str]:
    """把长文本切成适合卡片展示的短要点。"""
    text = str(value or "").strip()
    if not text:
        return []
    points = [
        item.strip(" ，,、")
        for item in re.split(r"[。\n；;!?！？]", text)
        if item and item.strip(" ，,、")
    ]
    return points[:limit]


def _build_spec_decision_impact(label: str) -> str:
    """把参数字段翻译成“为什么重要”的判断提示。"""
    field = str(label or "").strip()
    if any(token in field for token in ("电池", "续航", "充电")):
        return "更直接决定全天使用时的安心感。"
    if any(token in field for token in ("价格", "预算")):
        return "更适合用来解释预算边界和取舍成本。"
    if any(token in field for token in ("影像", "拍照", "镜头")):
        return "更适合解释这类体验为什么会影响偏好判断。"
    if any(token in field for token in ("性能", "芯片", "跑分")):
        return "更适合解释重度使用和长期流畅度。"
    return "更适合作为理解这页内容时的辅助依据。"


def _build_metric_reason(label: str, value: int) -> str:
    """给雷达维度补上一句可直接展示的解释。"""
    field = str(label or "").strip() or "该维度"
    if value >= 88:
        return f"{field} 已经形成明确优势，适合写进结论区。"
    if value >= 76:
        return f"{field} 表现稳定，更适合写成“没有明显短板”。"
    return f"{field} 更像取舍提醒，需要用更克制的口吻解释边界。"


def _build_metric_confidence(kind: str) -> str:
    """把事实状态映射成前端可读的置信度。"""
    if kind == "verified":
        return "high"
    if kind == "caution":
        return "low"
    return "medium"


def _build_source_items_from_titles(source_titles: list[str] | None, fact_sources: list[dict[str, Any]] | None, *, limit: int = 3) -> list[dict[str, str]]:
    """把纯来源标题映射成可点击的来源对象。"""
    normalized_titles = [str(item).strip() for item in (source_titles or []) if str(item).strip()]
    if not normalized_titles:
        return []

    indexed_fact_sources = [item for item in (fact_sources or []) if isinstance(item, dict)]
    picked: list[dict[str, str]] = []
    seen: set[str] = set()
    for title in normalized_titles:
        for source in indexed_fact_sources:
            source_title = str(source.get("title") or "").strip()
            if source_title != title:
                continue
            url = str(source.get("url") or "").strip()
            source_scope = str(source.get("source_scope") or "").strip()
            key = f"{title}::{url}"
            if key in seen:
                continue
            seen.add(key)
            picked.append({"label": title, "url": url, "source_scope": source_scope})
            break
        if len(picked) >= limit:
            break
    return picked


def build_component_contract_context(comp_type: str) -> dict[str, Any]:
    """从 manifest 读取组件契约，并压缩成给 worker 的上下文。"""
    normalized_type = normalize_component_type(comp_type) or comp_type
    return {
        "type": normalized_type,
        "label": get_component_label(normalized_type) or str(normalized_type),
        "semantic_role": get_component_semantic_role(normalized_type) or "content",
        "required_props": get_required_props(normalized_type),
        "optional_props": get_optional_props(normalized_type),
        "editable_targets": get_editable_targets(normalized_type),
        "asset_support": get_asset_support(normalized_type) or "none",
        "fact_binding_support": supports_fact_binding(normalized_type),
        "theme_slots": get_theme_slots(normalized_type),
        "quick_actions": get_quick_actions(normalized_type),
    }


def _clip_text(value: Any, limit: int = 220) -> str:
    """裁剪长文本，避免 brief 过长。"""
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _pick_document_guidance_summary(content_msgs: list[Any]) -> str:
    """从内容消息里挑出最后一层高信号导引摘要。"""
    for msg in reversed(content_msgs or []):
        content = getattr(msg, "content", None)
        summary = _clip_text(content, 240)
        if summary:
            return summary
    return "未提供额外导引"


def _nonempty_keys(payload: dict[str, Any] | None) -> list[str]:
    """列出 payload 里真正有值的字段。"""
    return [
        str(key)
        for key, value in (payload or {}).items()
        if value not in (None, "", [], {})
    ]


def _is_placeholder_image_url(value: Any) -> bool:
    """判断图片链接是否只是示意性占位地址。"""
    url = str(value or "").strip().lower()
    if not url:
        return False
    return any(token in url for token in ("example.com", "picsum.photos", "placeholder"))


def _sanitize_component_media_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """统一清洗组件 payload 中的假图链接。"""
    cleaned = deepcopy(payload or {})
    if not isinstance(cleaned, dict):
        return {}
    if isinstance(cleaned.get("image_urls"), list):
        cleaned["image_urls"] = [
            str(item).strip()
            for item in (cleaned.get("image_urls") or [])
            if str(item or "").strip() and not _is_placeholder_image_url(item)
        ]
    if _is_placeholder_image_url(cleaned.get("image_url")):
        cleaned.pop("image_url", None)
    return cleaned


def apply_component_contract_with_trace(comp_type: str, payload: dict[str, Any] | None, fallback_data: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """按 manifest 契约过滤、合并并审计 builder 输出。"""
    normalized_type = normalize_component_type(comp_type) or comp_type
    required_props = get_required_props(normalized_type)
    optional_props = get_optional_props(normalized_type)
    sanitized_payload = _sanitize_component_media_payload(payload)
    sanitized_fallback = _sanitize_component_media_payload(fallback_data)
    filtered_payload = filter_payload_for_component(normalized_type, sanitized_payload)
    filtered_fallback = filter_payload_for_component(normalized_type, sanitized_fallback)
    payload_keys = set(_nonempty_keys(sanitized_payload))
    fallback_keys = set(_nonempty_keys(sanitized_fallback))
    filtered_payload_keys = set(_nonempty_keys(filtered_payload))
    filtered_fallback_keys = set(_nonempty_keys(filtered_fallback))
    merged = enforce_component_contract(normalized_type, filtered_payload, filtered_fallback)
    final_payload = filter_payload_for_component(normalized_type, merged)
    precheck_missing_required = [
        field
        for field in required_props
        if filtered_payload.get(field) in (None, "", [], {})
    ]
    final_missing_required = [
        field
        for field in required_props
        if final_payload.get(field) in (None, "", [], {})
    ]
    contract_trace = {
        "normalized_type": normalized_type,
        "required_prop_count": len(required_props),
        "optional_prop_count": len(optional_props),
        "payload_field_count": len(payload_keys),
        "fallback_field_count": len(fallback_keys),
        "dropped_payload_fields": sorted(payload_keys - filtered_payload_keys),
        "dropped_fallback_fields": sorted(fallback_keys - filtered_fallback_keys),
        "contract_filter_count": len(payload_keys - filtered_payload_keys) + len(fallback_keys - filtered_fallback_keys),
        "precheck_warnings": [f"missing_required_before_merge:{field}" for field in precheck_missing_required],
        "precheck_warning_count": len(precheck_missing_required),
        "final_missing_required": final_missing_required,
    }
    return final_payload, contract_trace


def apply_component_contract_layer(comp_type: str, payload: dict[str, Any] | None, fallback_data: dict[str, Any] | None) -> dict[str, Any]:
    """只返回最终契约化 payload，供不需要 trace 的调用方复用。"""
    final_payload, _ = apply_component_contract_with_trace(comp_type, payload, fallback_data)
    return final_payload


def build_component_block_patch(
    task_state: dict[str, Any],
    *,
    comp_id: str,
    comp_type: str,
    content_brief: str,
    props: dict[str, Any],
    style: dict[str, Any],
) -> dict[str, Any]:
    """把 builder 结果压成块级原子 patch，避免并发 worker 互相覆盖整页文档。"""
    note_document = build_note_document_from_state(task_state)
    existing_blocks = list(note_document.get("blocks") or [])
    block_exists = any(str(block.get("id") or "") == comp_id for block in existing_blocks)
    patch: dict[str, Any] = {
        "_block_update": {
            "id": comp_id,
            "data": {
                "type": comp_type,
                "content_brief": content_brief,
                "props": deepcopy(props or {}),
                "style": deepcopy(style or {}),
            },
        }
    }
    if not block_exists:
        patch["_block_append"] = {
            "id": comp_id,
            "type": comp_type,
            "content_brief": content_brief,
            "props": {},
            "style": {},
            "asset_refs": [],
            "fact_bindings": [],
            "editable_targets": get_editable_targets(comp_type),
            "asset_support": get_asset_support(comp_type),
            "fact_binding_support": supports_fact_binding(comp_type),
            "order": len(existing_blocks),
        }
    return patch

def build_component_fallback(
    comp_type: str,
    comp_id: str,
    content_brief: str,
    user_query: str,
    retrieved_knowledge: Any,
    image_assets: list[dict[str, Any]],
    *,
    active_archetype: str = "general",
    user_provided_facts: dict[str, Any] | None = None,
) -> dict:
    """在模型输出不足时，为不同组件生成安全 fallback 数据。"""
    knowledge = retrieved_knowledge if isinstance(retrieved_knowledge, dict) else {}
    entity_name = normalize_entity_name(knowledge.get("entity_name") or user_query)
    attrs = knowledge.get("core_attributes") or {}
    selling_points = knowledge.get("key_selling_points") or []
    known_issues = knowledge.get("known_issues") or []
    summary = knowledge.get("summary") or content_brief or user_query
    confirmed_summaries = summarize_confirmed_attributes(knowledge)
    conflict_safe_notes = build_conflict_safe_notes(knowledge)
    valid_assets = [
        asset
        for asset in image_assets
        if isinstance(asset, dict)
        and asset.get("url")
        and str(asset.get("selection_state") or "").strip().lower() != "excluded"
        and not _is_placeholder_image_url(asset.get("url"))
    ]

    def _asset_priority(item: dict[str, Any]) -> tuple[int, int, int]:
        role = str(item.get("role") or "").strip().lower()
        locked = bool(item.get("locked"))
        if comp_type == "CoverSwiper":
            role_priority = 0 if role == "cover" else (1 if role == "inline" else 2)
        elif comp_type in {"WeatherPolaroid"}:
            role_priority = 0 if role == "inline" else (1 if role == "cover" else 2)
        else:
            role_priority = 0 if role == "inline" else (1 if role == "cover" else 2)
        return (0 if locked else 1, role_priority, 0)

    prioritized_assets = sorted(valid_assets, key=_asset_priority)
    image_urls = [
        str(asset.get("url")).strip()
        for asset in prioritized_assets
    ]
    verified_feature_items = [f"{VERIFIED_FEATURE_PREFIX}{item}" for item in confirmed_summaries]
    fact_sources = [item for item in (knowledge.get("fact_sources") or []) if isinstance(item, dict)]
    user_fact_text = str((user_provided_facts or {}).get("raw_text") or "").strip()
    slot_summaries = {
        str(key): str((value or {}).get("summary") or "").strip()
        for key, value in (knowledge.get("fact_slots") or {}).items()
        if isinstance(value, dict) and str((value or {}).get("summary") or "").strip()
    }

    if comp_type == "TitleBlock":
        return {"type": comp_type, "title": content_brief or entity_name}
    if comp_type == "StoryText":
        paragraphs = []
        paragraph_meta = []
        sections = []
        if summary:
            paragraphs.append(summary)
            paragraph_meta.append({"kind": "default", "sources": [], "source_items": [], "hint": "页面摘要"})
            sections.append({
                "label": "开场判断",
                "role": "summary",
                "paragraph": summary,
                "summary": "先把读者最该记住的判断说清楚。",
                "source_items": [],
            })
        if confirmed_summaries:
            confirmed_text = "已确认参数：" + " / ".join(confirmed_summaries[:3])
            paragraphs.append("已确认参数：" + " / ".join(confirmed_summaries[:3]))
            confirmed_sources = []
            for payload in (knowledge.get("confirmed_facts") or {}).values():
                for source in (payload.get("sources") or []):
                    source_text = str(source).strip()
                    if source_text and source_text not in confirmed_sources:
                        confirmed_sources.append(source_text)
            paragraph_meta.append({
                "kind": "verified",
                "sources": confirmed_sources[:4],
                "source_items": _build_source_items_from_titles(confirmed_sources[:4], fact_sources),
                "hint": "该段采用已确认事实",
                "fields": list((knowledge.get("confirmed_facts") or {}).keys()),
            })
            sections.append({
                "label": "已确认事实",
                "role": "verified",
                "paragraph": confirmed_text,
                "summary": "这部分适合承接官方或高可信的已确认信息。",
                "sources": confirmed_sources[:4],
                "source_items": _build_source_items_from_titles(confirmed_sources[:4], fact_sources),
            })
        elif slot_summaries:
            slot_text = "已补充信息：" + " / ".join(list(slot_summaries.values())[:2])
            paragraphs.append(slot_text)
            paragraph_meta.append({
                "kind": "verified",
                "sources": [str(item.get("title") or "").strip() for item in fact_sources[:3] if str(item.get("title") or "").strip()],
                "source_items": _build_source_items_from_titles(
                    [str(item.get("title") or "").strip() for item in fact_sources[:3] if str(item.get("title") or "").strip()],
                    fact_sources,
                ),
                "hint": "该段采用了按块补搜后的关键字段。",
                "fields": list(slot_summaries.keys()),
            })
            sections.append({
                "label": "补齐信息",
                "role": "verified",
                "paragraph": slot_text,
                "summary": "这里补的是当前积木真正缺的关键信息。",
                "sources": [str(item.get("title") or "").strip() for item in fact_sources[:3] if str(item.get("title") or "").strip()],
                "source_items": _build_source_items_from_titles(
                    [str(item.get("title") or "").strip() for item in fact_sources[:3] if str(item.get("title") or "").strip()],
                    fact_sources,
                ),
            })
        if conflict_safe_notes:
            caution_text = "参数提示：" + " / ".join(conflict_safe_notes[:2])
            paragraphs.append(caution_text)
            caution_sources = []
            for conflict in (knowledge.get("fact_conflicts") or []):
                for value in (conflict.get("values") or []):
                    for source in (value.get("sources") or []):
                        source_text = str(source).strip()
                        if source_text and source_text not in caution_sources:
                            caution_sources.append(source_text)
            paragraph_meta.append({
                "kind": "caution",
                "sources": caution_sources[:4],
                "source_items": _build_source_items_from_titles(caution_sources[:4], fact_sources),
                "hint": "该段因参数冲突而采用保守表达",
                "fields": [str(conflict.get("field") or "") for conflict in (knowledge.get("fact_conflicts") or []) if str(conflict.get("field") or "")],
            })
            sections.append({
                "label": "边界提醒",
                "role": "caution",
                "paragraph": caution_text,
                "summary": "这里更适合提醒读者哪里需要保守判断。",
                "sources": caution_sources[:4],
                "source_items": _build_source_items_from_titles(caution_sources[:4], fact_sources),
            })
        if selling_points:
            selling_text = "亮点: " + " / ".join(selling_points[:3])
            paragraphs.append(selling_text)
            paragraph_meta.append({"kind": "default", "sources": [], "source_items": [], "hint": "卖点提炼"})
            sections.append({
                "label": "亮点展开",
                "role": "selling_point",
                "paragraph": selling_text,
                "summary": "适合把最容易打动人的理由收在这里。",
                "source_items": [],
            })
        if not paragraphs:
            paragraphs.append(content_brief or "内容整理中")
            paragraph_meta.append({"kind": "default", "sources": [], "source_items": [], "hint": "基础内容占位"})
            sections.append({
                "label": "正文",
                "role": "body",
                "paragraph": content_brief or "内容整理中",
                "summary": "等待进一步补齐。",
                "source_items": [],
            })
        return {"type": comp_type, "paragraphs": paragraphs, "paragraph_meta": paragraph_meta, "sections": sections}
    if comp_type == "ProductSpecCard":
        feature_meta = []
        features = []
        spec_items = []
        confirmed_facts = knowledge.get("confirmed_facts") or {}
        for item in confirmed_summaries[:4]:
            features.append(f"{VERIFIED_FEATURE_PREFIX}{item}")
            matched_sources = []
            matched_field = None
            for payload in confirmed_facts.values():
                label = str(payload.get("field_label") or "")
                value = str(payload.get("value") or "")
                if label and value and item == f"{label}: {value}":
                    matched_sources = [str(source) for source in (payload.get("sources") or [])]
                    break
            matched_field = next((field for field, payload in confirmed_facts.items() if f"{payload.get('field_label')}: {payload.get('value')}" == item), None)
            feature_meta.append({"kind": "verified", "sources": matched_sources, "hint": "该参数已由用户人工确认", "field": matched_field})
            feature_meta[-1]["source_items"] = _build_source_items_from_titles(matched_sources, fact_sources)
            label, value = item.split(":", 1) if ":" in item else (item, "")
            spec_items.append({
                "label": label.strip(),
                "value": value.strip(),
                "status": "verified",
                "decision_impact": _build_spec_decision_impact(label),
                "sources": matched_sources,
                "source_items": _build_source_items_from_titles(matched_sources, fact_sources),
                "confidence": "high",
                "hint": "该参数已由用户人工确认",
            })

        for attr_text in [f"{k}: {v}" for k, v in list(attrs.items())[:6] if f"{k}: {v}" not in confirmed_summaries]:
            features.append(attr_text)
            matching_sources = [str(item.get("title") or "").strip() for item in fact_sources[:3] if str(item.get("title") or "").strip()]
            feature_meta.append({"kind": "default", "sources": matching_sources, "source_items": _build_source_items_from_titles(matching_sources, fact_sources), "hint": "当前结构化事实库参数", "field": attr_text.split(":", 1)[0] if ":" in attr_text else None})
            label, value = attr_text.split(":", 1) if ":" in attr_text else (attr_text, "")
            spec_items.append({
                "label": label.strip(),
                "value": value.strip(),
                "status": "default",
                "decision_impact": _build_spec_decision_impact(label),
                "sources": matching_sources,
                "source_items": _build_source_items_from_titles(matching_sources, fact_sources),
                "confidence": "medium",
                "hint": "当前结构化事实库参数",
            })

        conflict_map = {str(item.get("field") or ""): item for item in (knowledge.get("fact_conflicts") or []) if isinstance(item, dict)}
        for note in conflict_safe_notes[:2]:
            if note not in features:
                features.append(note)
                matched_sources = []
                for field_name, conflict in conflict_map.items():
                    label = str(field_name)
                    if note.startswith("电池容量") and field_name == "battery_capacity":
                        matched_sources = sorted({str(src) for value in (conflict.get("values") or []) for src in (value.get("sources") or [])})[:4]
                        break
                    if note.startswith("价格") and field_name == "price":
                        matched_sources = sorted({str(src) for value in (conflict.get("values") or []) for src in (value.get("sources") or [])})[:4]
                        break
                feature_meta.append({"kind": "caution", "sources": matched_sources, "hint": "该参数存在冲突，已自动采用保守表达", "field": "battery_capacity" if note.startswith("电池容量") else ("price" if note.startswith("价格") else None)})
                feature_meta[-1]["source_items"] = _build_source_items_from_titles(matched_sources, fact_sources)
                label, value = note.split(":", 1) if ":" in note else (note, "")
                spec_items.append({
                    "label": label.strip(),
                    "value": value.strip(),
                    "status": "caution",
                    "decision_impact": "这里更适合提醒读者注意边界，而不是直接写死结论。",
                    "sources": matched_sources,
                    "source_items": _build_source_items_from_titles(matched_sources, fact_sources),
                    "confidence": "low",
                    "hint": "该参数存在冲突，已自动采用保守表达",
                })

        if not features:
            features = selling_points[:4] or [content_brief or "核心参数整理中"]
            feature_meta = [{"kind": "default", "sources": [], "hint": "基础参数摘要"} for _ in features]
            spec_items = [
                {
                    "label": f"判断点 {idx + 1}",
                    "value": str(item),
                    "status": "default",
                    "decision_impact": "更适合作为理解这页内容时的补充说明。",
                    "sources": [],
                    "source_items": [],
                    "confidence": "medium",
                    "hint": "基础参数摘要",
                }
                for idx, item in enumerate(features)
            ]
        mode = "purchase_judgment"
        if active_archetype in {"gourmet", "food"}:
            mode = "store_facts"
        elif active_archetype not in {"seeding"}:
            mode = "neutral_facts"
        return {"type": comp_type, "mode": mode, "core_features": features, "feature_meta": feature_meta, "spec_items": spec_items}
    if comp_type == "CoverSwiper":
        cover_title = content_brief or f"{entity_name} 封面"
        frame_headlines = [f"封面视角 {idx + 1}" for idx in range(min(len(image_urls[:5]), 5))]
        frame_captions = [
            "补充当前主题的核心画面和氛围。"
            for _ in range(min(len(image_urls[:5]), 5))
        ]
        if frame_headlines:
            frame_headlines[0] = cover_title
        if frame_captions:
            frame_captions[0] = summary or "这张图负责把当前主题的第一眼重点讲清楚。"
        return {
            "type": comp_type,
            "image_urls": image_urls[:5],
            "title": cover_title,
            "description": summary or "补充当前主题的核心画面和氛围。",
            "deck_summary": f"共 {max(len(image_urls[:5]), 1)} 张图，适合承接首屏氛围、补充视角和封面说明。",
            "cover_focus": "封面对齐当前主题",
            "frame_headlines": frame_headlines,
            "frame_captions": frame_captions,
        }
    if comp_type == "RadarChartBlock":
        dimensions = ["性能", "影像", "续航", "设计", "体验"]
        score_seed = min(95, 60 + len(selling_points) * 5)
        scores = [score_seed, score_seed - 4, score_seed - 8, score_seed - 2, score_seed - 6]
        metrics = []
        evidence_labels = confirmed_summaries[:3] or selling_points[:3]
        for idx, label in enumerate(dimensions):
            status = "verified" if idx < len(confirmed_summaries) else ("caution" if idx == len(dimensions) - 1 and conflict_safe_notes else "default")
            metrics.append({
                "label": label,
                "value": scores[idx],
                "reason": _build_metric_reason(label, scores[idx]),
                "confidence": _build_metric_confidence(status),
                "evidence": evidence_labels[idx % len(evidence_labels)] if evidence_labels else f"{label} 表现较为突出",
            })
        return {"type": comp_type, "mode": "judgment_summary", "dimensions": dimensions, "scores": scores, "metrics": metrics}
    if comp_type == "PollBlock":
        option_a = selling_points[0] if selling_points else "影像表现"
        option_b = known_issues[0] if known_issues else "价格门槛"
        return {
            "type": comp_type,
            "question": f"{entity_name} 最打动你的是哪一点？",
            "option_a": option_a,
            "option_b": option_b,
            "option_cards": [
                {
                    "label": option_a,
                    "stance": "主推理由",
                    "vote_hint": "如果你更看重第一眼打动力，就会偏向这一边。",
                    "why_it_matters": "适合承接明显优势和第一购买理由。",
                },
                {
                    "label": option_b,
                    "stance": "现实代价",
                    "vote_hint": "如果你更在意长期成本或边界，就会更容易站这边。",
                    "why_it_matters": "适合把用户真正会犹豫的点显性化。",
                },
            ],
        }
    if comp_type == "VersusCard":
        battle_report = knowledge.get("battle_report") or {}
        pro_summary = battle_report.get("pros", {}).get("summary") or (selling_points[0] if selling_points else "优势整理中")
        con_summary = battle_report.get("cons", {}).get("summary") or (known_issues[0] if known_issues else "短板整理中")
        pro_details = battle_report.get("pros", {}).get("details") or " / ".join(selling_points[:3]) or "适合先讲亮点和主推荐理由。"
        con_details = battle_report.get("cons", {}).get("details") or " / ".join(known_issues[:3]) or "适合把代价和边界说透。"
        return {
            "type": comp_type,
            "title": battle_report.get("title") or "优缺点速览",
            "pros": {
                "summary": pro_summary,
                "details": pro_details,
                "points": battle_report.get("pros", {}).get("points") or _split_readable_points(pro_details),
                "fit_for": battle_report.get("pros", {}).get("fit_for") or "适合更看重主推荐理由、上手好感和亮点整合的人。",
            },
            "cons": {
                "summary": con_summary,
                "details": con_details,
                "points": battle_report.get("cons", {}).get("points") or _split_readable_points(con_details),
                "fit_for": battle_report.get("cons", {}).get("fit_for") or "适合更看重代价、边界和真实妥协点的人。",
            },
            "decision_hint": battle_report.get("decision_hint") or "别把它当优缺点堆砌，而要把它看成两种选择路线的分流。",
            "risk_note": battle_report.get("risk_note") or "如果两边都很长，就说明内容还没被压成真正可决策的对比卡。",
        }
    if comp_type == "LocationBlock":
        location_text = (
            slot_summaries.get("transport")
            or slot_summaries.get("route")
            or slot_summaries.get("duration")
            or summary
        )
        return {"type": comp_type, "mode": "recommended", "poi_name": entity_name, "location": location_text}
    if comp_type == "WeatherPolaroid":
        return {
            "type": comp_type,
            "mode": "confirmed_snapshot" if user_fact_text else "ambience",
            "image_url": image_urls[0] if image_urls else None,
            "desc": slot_summaries.get("atmosphere") or summary,
            **({"time": "用户补充时段"} if user_fact_text else {}),
        }
    if comp_type == "TimelineBlock":
        timeline_seed = (
            [("用户补充", user_fact_text)]
            if user_fact_text
            else [
                ("上午", slot_summaries.get("transport") or "先把交通方式和第一站安排清楚，避免前半天被路程拖慢。"),
                ("下午", slot_summaries.get("route") or "先抓住最值得逛的主线，再把补充点位往后顺延。"),
                ("收尾", slot_summaries.get("duration") or "预留一点机动时间给散步、拍照和临时起意的停留。"),
            ]
        )
        return {
            "type": comp_type,
            "mode": "user_journal" if user_fact_text else "recommended",
            "events": [
                {
                    "timestamp": label,
                    "title": label,
                    "description": text,
                }
                for label, text in timeline_seed
                if text
            ],
        }
    if comp_type == "QuoteBlock":
        return {
            "type": comp_type,
            "mode": "user_quote" if user_fact_text else "summary",
            "quote": user_fact_text or summary or content_brief or "把这段重点浓缩成一句话总结。",
            "author": "用户补充" if user_fact_text else "",
        }
    return {"type": comp_type, "title": content_brief or "内容整理中"}


def enforce_component_contract(comp_type: str, result_data: dict, fallback_data: dict) -> dict:
    """确保组件输出至少满足必填字段约束。"""
    merged = dict(result_data or {})
    required_fields_map = {
        "TitleBlock": ["title"],
        "StoryText": ["paragraphs"],
        "ProductSpecCard": ["core_features"],
        "RadarChartBlock": ["dimensions", "scores"],
        "PollBlock": ["question", "option_a", "option_b"],
        "VersusCard": ["title", "pros", "cons"],
        "CoverSwiper": ["image_urls"],
        "LocationBlock": ["poi_name", "location"],
        "WeatherPolaroid": ["desc"],
    }

    for field in required_fields_map.get(comp_type, []):
        value = merged.get(field)
        if value in (None, "", [], {}):
            fallback_value = fallback_data.get(field)
            if fallback_value not in (None, "", [], {}):
                merged[field] = fallback_value

    if "type" not in merged:
        merged["type"] = comp_type
    return merged

async def component_builder_node(state: ComponentTaskState) -> dict:
    """
    逐块构建组件的 contract-first 工兵节点。
    """
    comp_id = state["component_id"]
    comp_type = state["component_type"]
    content_brief = state.get("content_brief", "填充内容")
    user_query = state.get("user_query", "")
    planner_policy = state.get("planner_policy", {}) if isinstance(state.get("planner_policy", {}), dict) else {}
    component_contract = build_component_contract_context(comp_type)
    user_provided_facts = state.get("user_provided_facts", {}) if isinstance(state.get("user_provided_facts", {}), dict) else {}
    
    # 1. 先把事实、资产、策略压缩成小摘要，避免工兵重新“读全局”。
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    battle_report = None
    image_assets = state.get("image_assets", [])
    fact_summary = {"entity": "", "key_selling_points": [], "known_issues": [], "core_attributes": {}, "confirmed_facts": {}, "conflict_count": 0, "image_count": 0}
    if isinstance(retrieved_knowledge, dict):
        battle_report = retrieved_knowledge.get("battle_report")
        fact_summary = build_fact_summary(retrieved_knowledge, image_assets)
        fact_grounding = build_fact_grounding_context(retrieved_knowledge)
    else:
        fact_grounding = ""

    # 2. 文档导引只保留最后一层简报，避免内容历史直接灌进构建节点。
    content_msgs = state.get("content_messages", [])
    document_guidance_summary = _pick_document_guidance_summary(content_msgs)
    policy_summary = build_policy_summary(planner_policy)
    asset_summary = build_asset_summary(image_assets, limit=3)
    evidence_slice = build_retrieval_evidence_slice(retrieved_knowledge, semantic_role=component_contract.get("semantic_role"), limit=3)
    fact_summary_count = count_fact_summary_entries(fact_summary)
    asset_count = len([asset for asset in image_assets if asset.get("url")])

    async with _github_limiter:
        await asyncio.sleep(random.uniform(0.1, 0.2))
        print(f"👷 [并发工兵] 构建中: {comp_id} ({comp_type})")
        
        llm = get_builder_llm()
        structured_llm = llm.with_structured_output(ComponentBuilderOutput, method="function_calling")
        
        # 3. 提示词只围绕组件契约和局部简报，不再承担全局策划职责。
        system_prompt = render_string_prompt(
            "services/component_builder_system.md",
            comp_id=comp_id,
            comp_type=comp_type,
            component_contract=json.dumps(component_contract, ensure_ascii=False, indent=2),
            content_brief=content_brief,
            document_guidance=document_guidance_summary,
            fact_summary=json.dumps(fact_summary, ensure_ascii=False, indent=2),
            asset_summary=json.dumps(asset_summary, ensure_ascii=False, indent=2),
            planner_policy_summary=json.dumps(policy_summary, ensure_ascii=False, indent=2),
            fact_grounding=(
                (fact_grounding or "暂无已确认事实；若存在冲突，不要编造绝对参数。")
                + f"\n\n【🔎 Evidence Slice】\n{json.dumps(evidence_slice, ensure_ascii=False, indent=2)}"
            ),
            battle_report=json.dumps(battle_report, ensure_ascii=False, indent=2) if (comp_type == "VersusCard" and battle_report) else "",
        )
        prompt_snapshot = build_prompt_snapshot(
            "component_builder",
            system_prompt=system_prompt,
            user_prompt=f"请根据指令完成组件数据构建。用户指令：{user_query}",
        )

        try:
            fallback_data = build_component_fallback(
                comp_type=comp_type,
                comp_id=comp_id,
                content_brief=content_brief,
                user_query=user_query,
                retrieved_knowledge=retrieved_knowledge,
                image_assets=state.get("image_assets", []),
                active_archetype=state.get("active_archetype", "general"),
                user_provided_facts=user_provided_facts,
            )
            result: ComponentBuilderOutput = await structured_llm.ainvoke([
                ("system", system_prompt),
                ("human", f"请根据指令完成组件数据构建。用户指令：{user_query}")
            ])
            
            res_data = {}
            if result.data:
                res_data = result.data.model_dump(exclude_none=True)
            res_data["type"] = comp_type
            res_data, contract_trace = apply_component_contract_with_trace(comp_type, res_data, fallback_data)
            
            # 对比卡深度纠偏
            if comp_type == "VersusCard" and battle_report:
                res_data["title"] = battle_report.get('title')
                res_data["pros"] = {
                    "summary": battle_report.get("pros", {}).get("summary"),
                    "details": battle_report.get("pros", {}).get("details"),
                    "points": battle_report.get("pros", {}).get("points") or _split_readable_points(battle_report.get("pros", {}).get("details")),
                    "fit_for": battle_report.get("pros", {}).get("fit_for"),
                }
                res_data["cons"] = {
                    "summary": battle_report.get("cons", {}).get("summary"),
                    "details": battle_report.get("cons", {}).get("details"),
                    "points": battle_report.get("cons", {}).get("points") or _split_readable_points(battle_report.get("cons", {}).get("details")),
                    "fit_for": battle_report.get("cons", {}).get("fit_for"),
                }
                res_data["decision_hint"] = battle_report.get("decision_hint")
                res_data["risk_note"] = battle_report.get("risk_note")
            
            style_data = {"css_classes": "", "inline_styles": {}}
            if result.style:
                style_data = result.style.model_dump(exclude_none=True)

            return {
                "note_document": build_component_block_patch(
                    state,
                    comp_id=comp_id,
                    comp_type=comp_type,
                    content_brief=content_brief,
                    props=res_data,
                    style=style_data,
                ),
                "node_prompts": prompt_snapshot,
                "turn_trace": {
                    "component_builder": {
                        comp_id: {
                            "component_type": comp_type,
                            "semantic_role": component_contract.get("semantic_role"),
                            "required_props": component_contract.get("required_props", []),
                            "editable_targets": component_contract.get("editable_targets", []),
                            "contract_filter_count": contract_trace.get("contract_filter_count", 0),
                            "dropped_payload_fields": contract_trace.get("dropped_payload_fields", []),
                            "precheck_warnings": contract_trace.get("precheck_warnings", []),
                            "precheck_warning_count": contract_trace.get("precheck_warning_count", 0),
                            "prompt_mode": "compact_contract_first",
                            "fact_summary_count": fact_summary_count,
                            "asset_count": asset_count,
                            "fallback_used": False,
                            "contract_first": True,
                        }
                    }
                },
                "agent_backends": {"component_builder": "contract_first_worker"},
            }
        except Exception as e:
            print(f"🩹 [工兵自愈] {comp_id} 失败: {e}")
            fallback_data = build_component_fallback(
                comp_type=comp_type,
                comp_id=comp_id,
                content_brief=content_brief,
                user_query=user_query,
                retrieved_knowledge=retrieved_knowledge,
                image_assets=state.get("image_assets", []),
                active_archetype=state.get("active_archetype", "general"),
                user_provided_facts=user_provided_facts,
            )
            
            # 最后的兜底：如果是对比卡且已有对战摘要，直接硬填
            if comp_type == "VersusCard" and battle_report:
                 merged_data, contract_trace = apply_component_contract_with_trace("VersusCard", {
                        "type": "VersusCard",
                        "title": battle_report.get('title'),
                        "pros": {
                            "summary": battle_report.get("pros", {}).get("summary"),
                            "details": battle_report.get("pros", {}).get("details"),
                            "points": battle_report.get("pros", {}).get("points") or _split_readable_points(battle_report.get("pros", {}).get("details")),
                            "fit_for": battle_report.get("pros", {}).get("fit_for"),
                        },
                        "cons": {
                            "summary": battle_report.get("cons", {}).get("summary"),
                            "details": battle_report.get("cons", {}).get("details"),
                            "points": battle_report.get("cons", {}).get("points") or _split_readable_points(battle_report.get("cons", {}).get("details")),
                            "fit_for": battle_report.get("cons", {}).get("fit_for"),
                        },
                        "decision_hint": battle_report.get("decision_hint"),
                        "risk_note": battle_report.get("risk_note"),
                    }, fallback_data)
                 return {
                     "note_document": build_component_block_patch(
                         state,
                         comp_id=comp_id,
                         comp_type=comp_type,
                         content_brief=content_brief,
                         props=merged_data,
                         style={"css_classes": "opacity-90", "inline_styles": {}},
                     ),
                     "node_prompts": prompt_snapshot,
                     "turn_trace": {
                        "component_builder": {
                            comp_id: {
                                "component_type": comp_type,
                                "semantic_role": component_contract.get("semantic_role"),
                                "required_props": component_contract.get("required_props", []),
                                "editable_targets": component_contract.get("editable_targets", []),
                                "contract_filter_count": contract_trace.get("contract_filter_count", 0),
                                "dropped_payload_fields": contract_trace.get("dropped_payload_fields", []),
                                "precheck_warnings": contract_trace.get("precheck_warnings", []),
                                "precheck_warning_count": contract_trace.get("precheck_warning_count", 0),
                                "prompt_mode": "compact_contract_first",
                                "fact_summary_count": fact_summary_count,
                                "asset_count": asset_count,
                                "fallback_used": True,
                                "fallback_reason": str(e),
                                "contract_first": True,
                            }
                        }
                    },
                    "agent_backends": {"component_builder": "contract_first_worker"},
                }
            
            merged_data, contract_trace = apply_component_contract_with_trace(comp_type, {}, fallback_data)
            return {
                "note_document": build_component_block_patch(
                    state,
                    comp_id=comp_id,
                    comp_type=comp_type,
                    content_brief=content_brief,
                    props=merged_data,
                    style={"css_classes": "", "inline_styles": {}},
                ),
                "node_prompts": prompt_snapshot,
                "turn_trace": {
                    "component_builder": {
                        comp_id: {
                            "component_type": comp_type,
                            "semantic_role": component_contract.get("semantic_role"),
                            "required_props": component_contract.get("required_props", []),
                            "editable_targets": component_contract.get("editable_targets", []),
                            "contract_filter_count": contract_trace.get("contract_filter_count", 0),
                            "dropped_payload_fields": contract_trace.get("dropped_payload_fields", []),
                            "precheck_warnings": contract_trace.get("precheck_warnings", []),
                            "precheck_warning_count": contract_trace.get("precheck_warning_count", 0),
                            "prompt_mode": "compact_contract_first",
                            "fact_summary_count": fact_summary_count,
                            "asset_count": asset_count,
                            "fallback_used": True,
                            "fallback_reason": str(e),
                            "contract_first": True,
                        }
                    }
                },
                "agent_backends": {"component_builder": "contract_first_worker"},
            }

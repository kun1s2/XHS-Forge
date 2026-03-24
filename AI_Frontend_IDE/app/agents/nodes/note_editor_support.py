"""Support helpers for note editor targeting, scoring, and contract text.

These helpers are intentionally kept separate from `note_editor_node.py` so the
main node reads like an execution pipeline rather than a long list of semantic
matching tables and scoring utilities.
"""

import re
from copy import deepcopy
from typing import Any

from app.core.component_manifest import (
    build_component_contract_map,
    get_component_aliases,
    get_component_label,
    get_component_semantic_role,
    get_editable_targets,
    get_quick_actions,
    list_component_entries,
    normalize_component_type,
    resolve_component_for_block_intent,
)
from app.core.note_document import build_note_document


SUPPORTED_COMPONENTS = build_component_contract_map(stable_only=True)
COMPONENT_QUERY_ALIASES = {}
for entry in list_component_entries(stable_only=True):
    component_type = str(entry.get("type") or "")
    if not component_type:
        continue
    COMPONENT_QUERY_ALIASES[component_type] = get_component_aliases(component_type)

THEME_PATCH_PRESETS = {
    "gray_blue": {
        "--bg-color": "#e2e8f0",
        "--primary-vibe": "#475569",
        "--surface-color": "#f8fafc",
        "--text-color": "#0f172a",
        "--muted-color": "#64748b",
        "--border-color": "#cbd5e1",
    },
    "minimalist": {
        "--bg-color": "#f8fafc",
        "--primary-vibe": "#334155",
        "--surface-color": "#ffffff",
        "--text-color": "#0f172a",
        "--muted-color": "#64748b",
        "--border-color": "#e2e8f0",
    },
    "cyberpunk": {
        "--bg-color": "#050505",
        "--primary-vibe": "#00f2ff",
        "--surface-color": "#111827",
        "--text-color": "#e0f2fe",
        "--muted-color": "#67e8f9",
        "--border-color": "#155e75",
    },
    "vintage": {
        "--bg-color": "#f4efe1",
        "--primary-vibe": "#7c5a3c",
        "--surface-color": "#fffaf1",
        "--text-color": "#4b3621",
        "--muted-color": "#8b6b4a",
        "--border-color": "#d6c2a1",
    },
    "luxury": {
        "--bg-color": "#111111",
        "--primary-vibe": "#d4af37",
        "--surface-color": "#1f1f1f",
        "--text-color": "#fef3c7",
        "--muted-color": "#e5c76b",
        "--border-color": "#6b5620",
    },
}

THEME_KEY_ALIASES = {
    "--primary-color": "--primary-vibe",
    "--accent-color": "--primary-vibe",
    "--secondary-color": "--muted-color",
    "--foreground-color": "--text-color",
}

COMPONENT_TYPE_ALIASES = {
    alias.lower(): component_type
    for component_type, aliases in COMPONENT_QUERY_ALIASES.items()
    for alias in aliases + [component_type, component_type.lower()]
}

MANIFEST_QUERY_HINTS = sorted(
    [
        (alias.lower(), component_type)
        for component_type, aliases in COMPONENT_QUERY_ALIASES.items()
        for alias in aliases + [component_type]
        if alias
    ],
    key=lambda item: len(item[0]),
    reverse=True,
)

PARAGRAPH_REFERENCE_RE = re.compile(r"第\s*[123一二三]\s*段")
GLOBAL_EDIT_INTENT_TOKENS = [
    "保留",
    "重写",
    "改",
    "修改",
    "优化",
    "调整",
    "简短",
    "简洁",
    "精简",
    "丰富",
    "删除",
    "删掉",
    "替换",
    "换成",
    "移动",
    "挪",
    "润色",
    "新增",
    "增加",
    "添加",
    "加一个",
    "来一个",
    "补一个",
    "插入",
]
EDIT_STYLE_HINT_TOKENS = [
    "收敛",
    "克制",
    "柔和",
    "锐利",
    "毒舌",
    "温和",
    "更强",
    "更弱",
]
COMPONENT_SIGNAL_TOKENS = sorted(
    {alias for aliases in COMPONENT_QUERY_ALIASES.values() for alias in aliases if alias},
    key=len,
    reverse=True,
)

ROLE_TOKEN_MAP = {
    "interactive_opinion": ["互动", "站队", "投票", "表态"],
    "narrative_text": ["正文", "文本", "段落", "结论", "文案", "总结"],
    "heading": ["标题", "大标题"],
    "hero_media": ["封面", "首图", "头图", "大图"],
    "evidence_summary": ["参数", "规格", "配置", "证据", "事实"],
    "comparison": ["对比", "优缺点", "pk", "vs"],
    "location_info": ["地点", "位置", "地址", "路线", "地图"],
    "ambience_snapshot": ["天气", "氛围", "感觉"],
}

EDITABLE_TARGET_TOKEN_MAP = {
    "title": ["标题"],
    "subtitle": ["副标题"],
    "paragraphs": ["正文", "文案", "段落", "结论"],
    "question": ["问题", "投票", "互动"],
    "option_a": ["选项", "投票"],
    "option_b": ["选项", "投票"],
    "core_features": ["参数", "规格", "配置", "证据", "事实"],
    "spec_items": ["参数标题", "参数表达", "参数项", "参数卡", "规格项"],
    "feature_meta": ["边界提醒", "确认提醒", "保守表达", "参数提醒"],
    "image_urls": ["封面", "配图", "图片", "首图"],
    "image_url": ["封面", "配图", "图片", "首图"],
    "description": ["说明", "文案", "画面说明", "首图说明", "图片说明"],
    "deck_summary": ["摘要", "下方说明", "轮播说明", "整体说明", "底部说明"],
    "frame_headlines": ["首图标题", "封面标题", "画面标题"],
    "frame_captions": ["首图文案", "画面文案", "图片文案", "轮播文案"],
    "metrics": ["结论摘要", "雷达总结", "维度理由", "判断说明"],
    "pros": ["优点", "正方", "支持", "左边", "左侧观点"],
    "cons": ["反方", "缺点", "槽点", "右边", "右侧观点"],
    "decision_hint": ["结论", "怎么选", "建议"],
    "risk_note": ["风险", "边界", "提醒"],
    "quote": ["引用", "金句"],
    "events": ["时间轴", "流程"],
}

ACTION_EDITABLE_TARGET_MAP = {
    "rewrite_paragraph": {"paragraphs"},
    "update_page_title": {"title", "subtitle"},
    "update_block": {"title", "subtitle", "paragraphs", "question", "option_a", "option_b", "core_features", "spec_items", "feature_meta", "image_url", "image_urls", "description", "deck_summary", "frame_headlines", "frame_captions", "metrics", "pros", "cons", "decision_hint", "risk_note", "quote", "events"},
    "append_block": set(),
}


def _mentions_paragraph_reference(query: str) -> bool:
    return bool(PARAGRAPH_REFERENCE_RE.search(query or ""))


def _has_edit_intent_language(query: str) -> bool:
    lowered = query or ""
    return any(token in lowered for token in GLOBAL_EDIT_INTENT_TOKENS) or any(token in lowered for token in EDIT_STYLE_HINT_TOKENS)


def _build_component_contract_text() -> str:
    lines = []
    for component_type, required_fields in SUPPORTED_COMPONENTS.items():
        editable_targets = get_editable_targets(component_type)
        semantic_role = get_component_semantic_role(component_type)
        quick_actions = get_quick_actions(component_type)
        label = get_component_label(component_type) or component_type
        editable_text = f" | 可编辑目标 {', '.join(editable_targets)}" if editable_targets else ""
        quick_action_text = f" | 快捷动作 {', '.join(quick_actions[:3])}" if quick_actions else ""
        lines.append(
            f"- {component_type} ({label}) | 语义 {semantic_role or 'content'}: 必填字段 {', '.join(required_fields)}{editable_text}{quick_action_text}"
        )
    return "\n".join(lines)


def _normalize_page_theme_patch(theme_patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(theme_patch, dict):
        return {}
    normalized = dict(theme_patch)
    for source_key, target_key in THEME_KEY_ALIASES.items():
        if source_key in normalized and target_key not in normalized:
            normalized[target_key] = normalized[source_key]
    if "--primary-vibe" in normalized and "--primary-color" not in normalized:
        normalized["--primary-color"] = normalized["--primary-vibe"]
    if "--muted-color" in normalized and "--secondary-color" not in normalized:
        normalized["--secondary-color"] = normalized["--muted-color"]
    return normalized


def _normalize_component_type_name(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    normalized = normalize_component_type(raw)
    if normalized:
        return normalized
    return COMPONENT_TYPE_ALIASES.get(raw.lower())


def _infer_component_type_from_query(query: str, *, exclude_type: str | None = None) -> str | None:
    lowered_query = (query or '').lower()
    normalized_exclude = _normalize_component_type_name(exclude_type)
    for alias, component_type in MANIFEST_QUERY_HINTS:
        if alias in lowered_query and component_type != normalized_exclude:
            return component_type
    return None


def _extract_component_mentions(user_query: str) -> list[tuple[int, str, str]]:
    mentions: list[tuple[int, str, str]] = []
    lowered_query = (user_query or "").lower()
    for alias, component_type in COMPONENT_TYPE_ALIASES.items():
        start = 0
        while True:
            idx = lowered_query.find(alias, start)
            if idx == -1:
                break
            mentions.append((idx, component_type, alias))
            start = idx + len(alias)
    mentions.sort(key=lambda item: (item[0], -len(item[2])))
    deduped: list[tuple[int, str, str]] = []
    seen = set()
    for idx, component_type, alias in mentions:
        key = (idx, component_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((idx, component_type, alias))
    return deduped


def _infer_replacement_component_type(user_query: str, explicit_type: str | None = None) -> str | None:
    normalized_explicit = _normalize_component_type_name(explicit_type)
    if normalized_explicit:
        return normalized_explicit

    query = user_query or ""
    for splitter in ["换成", "改成", "替换成", "改为", "变成"]:
        if splitter in query:
            suffix = query.split(splitter, 1)[1]
            inferred = _infer_component_type_from_query(suffix)
            if inferred:
                return inferred
            mentions = _extract_component_mentions(suffix)
            if mentions:
                return mentions[0][1]

    inferred = _infer_component_type_from_query(query)
    if inferred:
        return inferred
    mentions = _extract_component_mentions(query)
    return mentions[-1][1] if mentions else None


def _infer_component_type_from_planner_policy(
    user_query: str,
    planner_policy: dict[str, Any] | None = None,
) -> str | None:
    query = (user_query or "").lower()
    layout_policy = (planner_policy or {}).get("layout_policy") or {}
    preferred = [str(item) for item in list(layout_policy.get("preferred_block_intents") or []) if item]
    if not preferred:
        return None
    primary = str((planner_policy or {}).get("primary_scenario") or "").strip()
    scenario_scores = {primary: 1.0} if primary else {}
    for intent_type in preferred:
        tokens = ROLE_TOKEN_MAP.get(intent_type, [])
        if any(token in query for token in tokens):
            return resolve_component_for_block_intent(intent_type, scenario_scores=scenario_scores)
    return None


def _infer_component_type_from_note_document(
    user_query: str,
    note_document: dict[str, Any] | None = None,
) -> str | None:
    query = (user_query or "").lower()
    blocks = list((note_document or {}).get("blocks", []))
    if not blocks:
        return None
    scored: list[tuple[int, str]] = []
    for block in blocks:
        semantic_role = str(block.get("semantic_role") or "")
        block_type = _normalize_component_type_name(str(block.get("type") or ""))
        if not semantic_role or not block_type:
            continue
        tokens = ROLE_TOKEN_MAP.get(semantic_role, [])
        score = sum(1 for token in tokens if token in query)
        if score > 0:
            scored.append((score, block_type))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _infer_target_component_type(
    user_query: str,
    action: str,
    replacement_type: str | None = None,
    planner_policy: dict[str, Any] | None = None,
    note_document: dict[str, Any] | None = None,
) -> str | None:
    query = user_query or ""
    normalized_replacement_type = _normalize_component_type_name(replacement_type)

    if _mentions_paragraph_reference(query):
        return "StoryText"

    manifest_inferred = _infer_component_type_from_query(
        query,
        exclude_type=normalized_replacement_type if action == "replace_block" else None,
    )
    if manifest_inferred:
        return manifest_inferred

    policy_inferred = _infer_component_type_from_planner_policy(query, planner_policy)
    if policy_inferred and policy_inferred != normalized_replacement_type:
        return policy_inferred

    document_inferred = _infer_component_type_from_note_document(query, note_document)
    if document_inferred and document_inferred != normalized_replacement_type:
        return document_inferred

    mentions = _extract_component_mentions(user_query)
    if not mentions:
        return None

    if action == "replace_block":
        for _, component_type, _ in mentions:
            if component_type != normalized_replacement_type:
                return component_type
        return mentions[0][1]
    return mentions[0][1]


def _summarize_blocks(document_view: dict) -> str:
    blocks = list((document_view or {}).get("blocks", []))
    if not blocks:
        return "无"
    lines = []
    for index, block in enumerate(blocks[:8]):
        lines.append(
            f"{index}. id={block.get('id')} | type={block.get('component_type')} | brief={block.get('content_brief', '')}"
        )
    if len(blocks) > 8:
        lines.append(f"... 共 {len(blocks)} 个区块")
    return "\n".join(lines)


def _summarize_note_document_blocks(note_document: dict[str, Any]) -> str:
    blocks = list((note_document or {}).get("blocks", []))
    if not blocks:
        return "无"
    lines = []
    for index, block in enumerate(blocks[:8]):
        editable = ", ".join(block.get("editable_targets") or []) or "无"
        lines.append(
            f"{index}. id={block.get('id')} | type={block.get('type')} | role={block.get('semantic_role')} | editable={editable} | brief={block.get('content_brief', '')}"
        )
    if len(blocks) > 8:
        lines.append(f"... 共 {len(blocks)} 个文档区块")
    return "\n".join(lines)


def _find_note_document_block(note_document: dict[str, Any], block_id: str | None) -> dict[str, Any] | None:
    if not block_id:
        return None
    for block in list((note_document or {}).get("blocks", [])):
        if str(block.get("id") or "") == str(block_id):
            return block
    return None


def _build_note_block_meta_map(
    note_document: dict[str, Any] | None = None,
    document_view: dict | None = None,
) -> dict[str, dict[str, Any]]:
    source_document = note_document if list((note_document or {}).get("blocks", [])) else build_note_document(document_view=document_view or {})
    return {
        str(block.get("id")): block
        for block in list((source_document or {}).get("blocks", []))
        if block.get("id")
    }


def _score_block_capability_match(block_meta: dict[str, Any], user_query: str) -> int:
    query = (user_query or "").lower()
    if not block_meta:
        return 0
    semantic_role = str(block_meta.get("semantic_role") or "").lower()
    editable_targets = [str(item).lower() for item in list(block_meta.get("editable_targets") or [])]
    score = 0
    for token in ROLE_TOKEN_MAP.get(semantic_role, []):
        if token in query:
            score += 3
    for target in editable_targets:
        normalized = target.replace('[0]', '').replace('[1]', '').replace('[2]', '')
        for token in EDITABLE_TARGET_TOKEN_MAP.get(normalized, []):
            if token in query:
                score += 2
    return score


def _score_block_action_match(action: str | None, block_meta: dict[str, Any], user_query: str) -> int:
    if not block_meta or not action:
        return 0
    editable_targets = {
        str(item).lower().replace('[0]', '').replace('[1]', '').replace('[2]', '')
        for item in list(block_meta.get("editable_targets") or [])
        if item
    }
    if not editable_targets:
        return 0
    desired_targets = ACTION_EDITABLE_TARGET_MAP.get(action) or set()
    matched_targets = desired_targets.intersection(editable_targets)
    if not matched_targets:
        return 0
    query = (user_query or "").lower()
    score = 2
    for target in matched_targets:
        for token in EDITABLE_TARGET_TOKEN_MAP.get(target, []):
            if token in query:
                score += 2
                break
    return score


def _score_block_manifest_hint_match(
    block: dict[str, Any],
    block_meta: dict[str, Any],
    user_query: str,
) -> int:
    query = (user_query or "").lower()
    component_type = _normalize_component_type_name(
        str(block_meta.get("type") or block.get("component_type") or "")
    )
    if not component_type:
        return 0
    score = 0
    label = get_component_label(component_type).strip().lower()
    if label and label in query:
        score += 2
    for quick_action in get_quick_actions(component_type):
        action_text = str(quick_action).strip().lower()
        if action_text and action_text in query:
            score += 3
    return score


def _extract_planner_intent_hints(user_query: str, planner_policy: dict[str, Any] | None = None) -> set[str]:
    query = (user_query or "").lower()
    layout_policy = (planner_policy or {}).get("layout_policy") or {}
    preferred = {
        str(item)
        for item in list(layout_policy.get("preferred_block_intents") or [])
        if item
    }
    token_map = {
        "interactive_opinion": ["互动", "站队", "投票", "表态"],
        "narrative_text": ["正文", "文本", "段落", "结论", "文案", "总结"],
        "heading": ["标题", "大标题"],
        "hero_media": ["封面", "首图", "大图", "头图"],
        "evidence_summary": ["参数", "规格", "配置", "证据", "事实"],
        "comparison": ["对比", "优缺点", "pk", "vs"],
        "location_info": ["地点", "位置", "地址", "路线", "地图"],
        "ambience_snapshot": ["天气", "氛围", "感觉"],
    }
    hints: set[str] = set()
    for intent_type, tokens in token_map.items():
        if any(token in query for token in tokens):
            if not preferred or intent_type in preferred:
                hints.add(intent_type)
    return hints


def _score_block_planner_match(
    block_meta: dict[str, Any],
    user_query: str,
    planner_policy: dict[str, Any] | None = None,
) -> int:
    if not block_meta:
        return 0
    hints = _extract_planner_intent_hints(user_query, planner_policy)
    if not hints:
        return 0
    semantic_role = str(block_meta.get("semantic_role") or "")
    role_to_intent = {
        "interactive_opinion": "interactive_opinion",
        "narrative_text": "narrative_text",
        "heading": "heading",
        "hero_media": "hero_media",
        "evidence_summary": "evidence_summary",
        "comparison": "comparison",
        "location_info": "location_info",
        "ambience_snapshot": "ambience_snapshot",
    }
    intent_type = role_to_intent.get(semantic_role)
    return 4 if intent_type and intent_type in hints else 0


def _extract_query_terms(user_query: str) -> list[str]:
    lowered = (user_query or "").lower()
    raw_terms = re.findall(r"[a-z0-9_]{2,}|[一-鿿]{2,}", lowered)
    stop_terms = {"这个", "那个", "一下", "一点", "改得", "修改", "调整", "重写", "简短", "简洁", "更尖", "保留", "那块", "这个块", "一下子"}
    terms: list[str] = []

    def add_term(term: str) -> None:
        normalized = term.strip()
        if not normalized or normalized in stop_terms:
            return
        if normalized not in terms:
            terms.append(normalized)

    for term in raw_terms:
        normalized = term.strip()
        if not normalized:
            continue
        add_term(normalized)
        if re.fullmatch(r"[一-鿿]{2,}", normalized):
            for size in (2, 3):
                if len(normalized) <= size:
                    continue
                for idx in range(0, len(normalized) - size + 1):
                    add_term(normalized[idx: idx + size])
    return terms


def _extract_rewritable_payload_fields(payload: dict[str, Any]) -> dict[str, Any]:
    rewritable = {}
    for key in [
        "title",
        "subtitle",
        "question",
        "option_a",
        "option_b",
        "desc",
        "description",
        "deck_summary",
        "quote",
        "paragraphs",
        "frame_headlines",
        "frame_captions",
    ]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            rewritable[key] = value
        elif isinstance(value, list) and value and all(isinstance(item, str) for item in value):
            rewritable[key] = value
    metrics = payload.get("metrics")
    if isinstance(metrics, list):
        normalized_metrics = []
        for item in metrics:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            reason = str(item.get("reason") or "").strip()
            evidence = str(item.get("evidence") or "").strip()
            if label or reason or evidence:
                normalized_metrics.append({
                    "label": label,
                    "reason": reason,
                    "evidence": evidence,
                })
        if normalized_metrics:
            rewritable["metrics"] = normalized_metrics
    for key in ["spec_items", "feature_meta"]:
        value = payload.get(key)
        if isinstance(value, list):
            normalized_items = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                normalized = {
                    field: str(item.get(field) or "").strip()
                    for field in ("label", "value", "decision_impact", "hint")
                    if str(item.get(field) or "").strip()
                }
                if normalized:
                    normalized_items.append(normalized)
            if normalized_items:
                rewritable[key] = normalized_items
    for key in ["pros", "cons"]:
        value = payload.get(key)
        if isinstance(value, dict):
            summary = str(value.get("summary") or "").strip()
            points = [str(item).strip() for item in (value.get("points") or []) if str(item).strip()]
            fit_for = str(value.get("fit_for") or "").strip()
            if summary or points or fit_for:
                rewritable[key] = {
                    "summary": summary,
                    "points": points,
                    "fit_for": fit_for,
                }
    for key in ["decision_hint", "risk_note"]:
        value = str(payload.get(key) or "").strip()
        if value:
            rewritable[key] = value
    return rewritable


def _stringify_block_context(block: dict[str, Any], payload: dict[str, Any]) -> str:
    parts: list[str] = []
    brief = block.get("content_brief")
    if isinstance(brief, str) and brief.strip():
        parts.append(brief.strip().lower())
    rewritable = _extract_rewritable_payload_fields(payload)
    for value in rewritable.values():
        if isinstance(value, str) and value.strip():
            parts.append(value.strip().lower())
        elif isinstance(value, list):
            parts.extend(str(item).strip().lower() for item in value if isinstance(item, str) and item.strip())
            for item in value:
                if isinstance(item, dict):
                    parts.extend(str(field_value).strip().lower() for field_value in item.values() if isinstance(field_value, str) and field_value.strip())
    return " ".join(parts)


def _score_block_for_query(
    block: dict[str, Any],
    payload: dict[str, Any],
    user_query: str,
    inferred_target_type: str | None = None,
    block_meta: dict[str, Any] | None = None,
    planner_policy: dict[str, Any] | None = None,
    action: str | None = None,
) -> int:
    query = (user_query or "").lower()
    component_type = str(block.get("component_type") or "")
    if not component_type:
        return 0
    score = 0
    if inferred_target_type and component_type == inferred_target_type:
        score += 8
    for alias in COMPONENT_QUERY_ALIASES.get(component_type, []):
        alias_text = str(alias).strip().lower()
        if alias_text and alias_text in query:
            score += 3
    if _mentions_paragraph_reference(user_query) and component_type == "StoryText":
        score += 6
    brief_text = str(block.get("content_brief") or "").strip().lower()
    payload_text = _stringify_block_context({}, payload)
    context_text = " ".join(part for part in [brief_text, payload_text] if part)
    for term in _extract_query_terms(user_query):
        if term in brief_text:
            score += 3
        if term in payload_text:
            score += 2
        elif term in context_text:
            score += 1
    score += _score_block_capability_match(block_meta or {}, user_query)
    score += _score_block_action_match(action, block_meta or {}, user_query)
    score += _score_block_manifest_hint_match(block, block_meta or {}, user_query)
    score += _score_block_planner_match(block_meta or {}, user_query, planner_policy)
    return score


def _build_theme_patch_fallback(
    user_query: str,
    planner_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_query = (user_query or "").lower()
    theme_policy = (planner_policy or {}).get("theme_policy") or {}
    preset = str(theme_policy.get("preset") or "").lower()
    if any(token in raw_query for token in ["灰蓝", "蓝灰", "石板蓝", "slate blue"]):
        return deepcopy(THEME_PATCH_PRESETS["gray_blue"])
    if any(token in raw_query for token in ["黑金", "奢华", "高级黑", "luxury"]):
        return deepcopy(THEME_PATCH_PRESETS["luxury"])
    if any(token in raw_query for token in ["赛博", "霓虹", "cyberpunk", "neon"]):
        return deepcopy(THEME_PATCH_PRESETS["cyberpunk"])
    if any(token in raw_query for token in ["复古", "胶片", "vintage", "奶油"]):
        return deepcopy(THEME_PATCH_PRESETS["vintage"])
    if any(token in raw_query for token in ["极简", "简约", "克制", "minimalist"]):
        return deepcopy(THEME_PATCH_PRESETS["minimalist"])
    for preset_key in ["luxury", "cyberpunk", "vintage", "minimalist", "gray_blue"]:
        if preset_key in preset:
            return deepcopy(THEME_PATCH_PRESETS[preset_key])
    return {}

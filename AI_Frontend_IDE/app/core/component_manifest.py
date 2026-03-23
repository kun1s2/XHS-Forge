"""组件清单辅助模块。

`componentManifest.json` 是积木能力的唯一真相源。这里把常用读取逻辑收成
辅助函数，避免 resolver、builder、editor、renderer 在各处重复硬编码
组件契约。
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _manifest_path() -> Path:
    """返回前端 component manifest 的磁盘路径。"""
    return Path(__file__).resolve().parents[3] / "ai-frontend-ide" / "src" / "config" / "componentManifest.json"


@lru_cache(maxsize=1)
def load_component_manifest() -> dict[str, Any]:
    """读取并缓存完整的组件清单。"""
    with _manifest_path().open("r", encoding="utf-8") as f:
        return json.load(f)


def component_manifest_version() -> str:
    """返回当前组件清单版本号。"""
    return str(load_component_manifest().get("version") or "unknown")


def list_component_entries(*, stable_only: bool = False) -> list[dict[str, Any]]:
    """列出组件条目；可选只返回 stable 组件。"""
    entries = list(load_component_manifest().get("components") or [])
    if stable_only:
        entries = [entry for entry in entries if entry.get("stability") == "stable"]
    return entries


def get_component_entry(component_type: str | None) -> dict[str, Any] | None:
    """按组件类型读取单个组件条目。"""
    if not component_type:
        return None
    normalized = str(component_type).strip().lower()
    for entry in list_component_entries():
        if str(entry.get("type") or "").lower() == normalized:
            return entry
    return None


def get_component_alias_map(*, stable_only: bool = False) -> dict[str, str]:
    """构造 alias 到规范组件类型的映射表。"""
    alias_map: dict[str, str] = {}
    for entry in list_component_entries(stable_only=stable_only):
        component_type = str(entry.get("type") or "")
        for alias in list(entry.get("aliases") or []) + [component_type]:
            alias_map[str(alias).strip().lower()] = component_type
    return alias_map


def normalize_component_type(component_type: str | None) -> str | None:
    """把别名或大小写混杂的组件名归一化成正式组件类型。"""
    if not component_type:
        return None
    raw = str(component_type).strip()
    entry = get_component_entry(raw)
    if entry:
        return str(entry.get("type"))
    return get_component_alias_map().get(raw.lower())


def list_supported_component_types(*, stable_only: bool = False) -> list[str]:
    """列出当前支持的组件类型。"""
    return [str(entry.get("type")) for entry in list_component_entries(stable_only=stable_only)]


def get_required_props(component_type: str | None) -> list[str]:
    """读取组件的必填 props。"""
    entry = get_component_entry(component_type)
    return [str(item) for item in (entry or {}).get("required_props", [])]


def get_optional_props(component_type: str | None) -> list[str]:
    """读取组件的可选 props。"""
    entry = get_component_entry(component_type)
    return [str(item) for item in (entry or {}).get("optional_props", [])]


def get_editable_targets(component_type: str | None) -> list[str]:
    """读取组件允许被编辑的目标字段。"""
    entry = get_component_entry(component_type)
    return [str(item) for item in (entry or {}).get("editable_targets", [])]


def get_component_semantic_role(component_type: str | None) -> str:
    """读取组件的语义职责。"""
    entry = get_component_entry(component_type)
    return str((entry or {}).get("semantic_role") or "")


def get_component_label(component_type: str | None) -> str:
    """读取组件的人类可读标签。"""
    entry = get_component_entry(component_type)
    normalized = normalize_component_type(component_type)
    return str((entry or {}).get("label") or normalized or "")


def get_supported_scenarios(component_type: str | None) -> list[str]:
    """读取组件适配的场景列表。"""
    entry = get_component_entry(component_type)
    return [str(item) for item in (entry or {}).get("supported_scenarios", [])]


def get_component_aliases(component_type: str | None) -> list[str]:
    """读取组件的别名集合。"""
    entry = get_component_entry(component_type)
    aliases = [str(item) for item in (entry or {}).get("aliases", []) if str(item)]
    normalized_type = normalize_component_type(component_type)
    if normalized_type and normalized_type not in aliases:
        aliases.append(normalized_type)
    return aliases


def get_asset_support(component_type: str | None) -> str:
    """读取组件的素材依赖级别。"""
    entry = get_component_entry(component_type)
    return str((entry or {}).get("asset_support") or "none")


def supports_fact_binding(component_type: str | None) -> bool:
    """判断组件是否支持事实绑定。"""
    entry = get_component_entry(component_type)
    return bool((entry or {}).get("fact_binding_support"))


def get_theme_slots(component_type: str | None) -> list[str]:
    """读取组件开放给主题系统的样式槽位。"""
    entry = get_component_entry(component_type)
    return [str(item) for item in (entry or {}).get("theme_slots", []) if str(item)]


def get_quick_actions(component_type: str | None) -> list[str]:
    """读取组件常见的快捷编辑动作提示。"""
    entry = get_component_entry(component_type)
    return [str(item) for item in (entry or {}).get("quick_actions", []) if str(item)]


def list_components_for_semantic_role(
    semantic_role: str,
    *,
    stable_only: bool = True,
    scenario_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """按语义职责筛出候选组件，可选再按场景过滤。"""
    if not semantic_role:
        return []
    scenario_names = [str(item) for item in (scenario_names or []) if str(item)]
    candidates = []
    for entry in list_component_entries(stable_only=stable_only):
        if str(entry.get("semantic_role") or "") != semantic_role:
            continue
        supported = [str(item) for item in list(entry.get("supported_scenarios") or []) if str(item)]
        if scenario_names and supported and not any(name in supported for name in scenario_names):
            continue
        candidates.append(entry)
    return candidates


def build_component_contract_map(*, stable_only: bool = True) -> dict[str, list[str]]:
    """构造组件到必填字段集合的简化契约映射。"""
    contract_map: dict[str, list[str]] = {}
    for entry in list_component_entries(stable_only=stable_only):
        contract_map[str(entry.get("type"))] = get_required_props(str(entry.get("type")))
    return contract_map


def filter_payload_for_component(component_type: str | None, payload: dict[str, Any] | None) -> dict[str, Any]:
    """按组件 contract 过滤 payload，去掉越权字段。"""
    if not isinstance(payload, dict):
        payload = {}
    normalized_type = normalize_component_type(component_type)
    if not normalized_type:
        return dict(payload)
    allowed = set(get_required_props(normalized_type) + get_optional_props(normalized_type) + ["type"])
    filtered = {key: value for key, value in payload.items() if key in allowed}
    filtered["type"] = normalized_type
    return filtered


def resolve_component_for_block_intent(
    intent_type: str,
    *,
    has_images: bool = False,
    scenario_scores: dict[str, float] | None = None,
) -> str:
    """把 block intent 解析成最合适的组件类型。"""
    scores = scenario_scores or {}
    ranked_scenarios = [
        name for name, score in sorted(scores.items(), key=lambda item: float(item[1] or 0.0), reverse=True)
        if float(score or 0.0) > 0
    ]

    if intent_type == "hero_media":
        role_candidates = list_components_for_semantic_role("hero_media", scenario_names=ranked_scenarios)
        if has_images:
            for entry in role_candidates:
                if get_asset_support(str(entry.get("type") or "")) == "required":
                    return str(entry.get("type"))
        for entry in role_candidates:
            if get_asset_support(str(entry.get("type") or "")) != "required":
                return str(entry.get("type"))
        return "CoverSwiper" if has_images else "WeatherPolaroid"

    if intent_type == "evidence_summary":
        role_candidates = list_components_for_semantic_role("evidence_summary", scenario_names=ranked_scenarios)
        seeding_weight = float(scores.get("seeding", 0.0))
        if seeding_weight >= 0.6:
            radar_like = next((entry for entry in role_candidates if str(entry.get("type") or "") == "ProductSpecCard"), None)
            score_overview = list_components_for_semantic_role("score_overview", scenario_names=ranked_scenarios)
            if score_overview:
                return str(score_overview[0].get("type"))
            if radar_like:
                return str(radar_like.get("type"))
        fact_bound = next((entry for entry in role_candidates if supports_fact_binding(str(entry.get("type") or ""))), None)
        if fact_bound:
            return str(fact_bound.get("type"))
        if role_candidates:
            return str(role_candidates[0].get("type"))

    role_candidates = list_components_for_semantic_role(intent_type, scenario_names=ranked_scenarios)
    if role_candidates:
        return str(role_candidates[0].get("type"))

    fallback_role_map = {
        "heading": "heading",
        "narrative_text": "narrative_text",
        "comparison": "comparison",
        "interactive_opinion": "interactive_opinion",
        "location_info": "location_info",
        "ambience_snapshot": "ambience_snapshot",
        "score_overview": "score_overview",
        "quote_highlight": "quote_highlight",
        "timeline": "timeline",
    }
    fallback_role = fallback_role_map.get(intent_type)
    if fallback_role:
        role_candidates = list_components_for_semantic_role(fallback_role, scenario_names=ranked_scenarios)
        if role_candidates:
            return str(role_candidates[0].get("type"))

    if intent_type == "heading":
        return "TitleBlock"
    if intent_type == "narrative_text":
        return "StoryText"
    if intent_type == "comparison":
        return "VersusCard"
    if intent_type == "interactive_opinion":
        return "PollBlock"
    if intent_type == "location_info":
        return "LocationBlock"
    if intent_type == "ambience_snapshot":
        return "WeatherPolaroid"
    if intent_type == "score_overview":
        return "RadarChartBlock"
    if intent_type == "quote_highlight":
        return "QuoteBlock"
    if intent_type == "timeline":
        return "TimelineBlock"
    return "StoryText"


def is_component_supported_for_verifier(component_type: str | None) -> bool:
    """判断组件是否进入 verifier 的正式支持范围。"""
    entry = get_component_entry(component_type)
    return bool(entry) and entry.get("stability") == "stable"


def is_component_supported_for_html(component_type: str | None) -> bool:
    """判断组件是否进入 HTML 导出的正式支持范围。"""
    entry = get_component_entry(component_type)
    return bool(entry) and bool(entry.get("html_renderer"))

"""持续笔记协作场景的正式检索 profile。"""

from __future__ import annotations

from typing import Any


_DIGITAL_HINTS = (
    "mate",
    "iphone",
    "小米",
    "华为",
    "苹果",
    "oppo",
    "vivo",
    "一加",
    "realme",
    "三星",
    "耳机",
    "相机",
    "手机",
    "平板",
    "显卡",
    "笔记本",
    "ultra",
    "pro",
    "max",
    "cpu",
    "芯片",
    "电池",
    "续航",
    "充电",
    "屏幕",
    "影像",
    "镜头",
    "soc",
)

_COMPONENT_SLOT_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "TitleBlock": (),
    "StoryText": ("core", "highlights"),
    "ProductSpecCard": ("core", "price"),
    "RadarChartBlock": ("core", "highlights"),
    "VersusCard": ("experience", "highlights"),
    "PollBlock": ("highlights",),
    "CoverSwiper": (),
    "QuoteBlock": ("highlights",),
}


def _normalize(text: str) -> str:
    return str(text or "").strip().lower()


def infer_retrieval_profile(*, user_query: str, entity_name: str, active_archetype: str | None) -> dict[str, Any]:
    query = _normalize(user_query)
    entity = _normalize(entity_name)
    archetype = _normalize(active_archetype or "")
    combined = f"{query} {entity}".strip()

    if archetype == "notes" or any(token in combined for token in _DIGITAL_HINTS):
        return {
            "profile_name": "digital_review",
            "domain": "digital_review",
            "critical_slot_keys": ["chipset", "battery", "charging", "price"],
            "slot_labels": {
                "chipset": "CPU / SoC",
                "battery": "电池与续航",
                "charging": "充电",
                "display": "屏幕",
                "camera": "影像",
                "price": "价格与版本",
            },
            "followup_limit": 3,
            "query_variants": [
                {"scope": "official", "query": f"{entity_name} 核心参数 价格 官方"},
                {"scope": "review", "query": f"{entity_name} 用户评价 真实体验"},
                {"scope": "chipset", "query": f"{entity_name} CPU SoC 处理器 官方 参数"},
                {"scope": "battery", "query": f"{entity_name} 电池容量 续航 官方 参数"},
                {"scope": "display", "query": f"{entity_name} 屏幕 参数 分辨率 亮度 官方"},
                {"scope": "camera", "query": f"{entity_name} 相机 影像 参数 官方"},
                {"scope": "price", "query": f"{entity_name} 价格 版本 官方"},
            ],
            "followup_queries": {
                "chipset": [f"{entity_name} 处理器 芯片 SoC 官方 参数"],
                "battery": [f"{entity_name} 电池容量 续航 官方 实测"],
                "charging": [f"{entity_name} 快充 充电功率 官方 参数"],
                "display": [f"{entity_name} 屏幕 尺寸 分辨率 峰值亮度 官方"],
                "camera": [f"{entity_name} 影像 传感器 焦段 官方 参数"],
                "price": [f"{entity_name} 售价 版本 官方 发售价"],
            },
        }

    return {
        "profile_name": "digital_grounded",
        "domain": "digital_review",
        "critical_slot_keys": ["core", "price"],
        "slot_labels": {
            "core": "核心事实",
            "price": "价格与版本",
            "highlights": "亮点",
        },
        "followup_limit": 3,
        "query_variants": [
            {"scope": "official", "query": f"{entity_name or user_query} 核心参数 价格 官方"},
            {"scope": "review", "query": f"{entity_name or user_query} 用户评价 真实体验"},
            {"scope": "price", "query": f"{entity_name or user_query} 价格 版本 官方"},
        ],
        "followup_queries": {
            "core": [f"{entity_name or user_query} 核心信息 官方"],
            "price": [f"{entity_name or user_query} 价格 版本 发售价 官方"],
            "highlights": [f"{entity_name or user_query} 亮点 推荐理由 真实体验"],
        },
    }


def extract_fact_slots(*, profile_name: str, results_by_scope: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    slots: dict[str, dict[str, Any]] = {}

    def _first_non_empty_snippet(scope: str) -> tuple[str, str, str]:
        for item in results_by_scope.get(scope, []):
            title = str(item.get("title") or "").strip()
            link = str(item.get("link") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if title or snippet:
                return title, snippet, link
        return "", "", ""

    scope_to_slot = {
        "official": "core",
        "review": "experience",
        "chipset": "chipset",
        "battery": "battery",
        "charging": "charging",
        "display": "display",
        "camera": "camera",
        "price": "price",
        "transport": "transport",
        "duration": "duration",
        "menu": "signature",
        "context": "context",
    }

    for scope, records in results_by_scope.items():
        slot = scope_to_slot.get(scope, scope)
        title, snippet, link = _first_non_empty_snippet(scope)
        if not (title or snippet):
            continue
        slots[slot] = {
            "scope": scope,
            "summary": snippet or title,
            "title": title,
            "url": link,
        }

    if profile_name == "digital_review" and "price" not in slots and "official" in results_by_scope:
        title, snippet, link = _first_non_empty_snippet("official")
        if snippet:
            slots["price"] = {"scope": "official", "summary": snippet, "title": title, "url": link}

    return slots


def compute_missing_fields(*, slot_labels: dict[str, str], fact_slots: dict[str, dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    for key, label in (slot_labels or {}).items():
        if key not in fact_slots:
            missing.append(label)
    return missing


def compute_missing_slot_keys(*, slot_labels: dict[str, str], fact_slots: dict[str, dict[str, Any]]) -> list[str]:
    """返回真正缺失的 slot key，供补搜链精确决策。"""
    return [
        str(key)
        for key in (slot_labels or {}).keys()
        if str(key) not in (fact_slots or {})
    ]


def build_followup_query_variants(
    *,
    user_query: str,
    entity_name: str,
    retrieval_profile: dict[str, Any] | None,
    missing_slot_keys: list[str] | None,
) -> list[dict[str, str]]:
    """根据缺失字段生成第二轮定向补搜 query。"""
    profile = retrieval_profile or {}
    subject = str(entity_name or user_query or "").strip() or "当前主题"
    slot_labels = {
        str(key): str(value)
        for key, value in (profile.get("slot_labels") or {}).items()
    }
    followup_templates = {
        str(key): value
        for key, value in (profile.get("followup_queries") or {}).items()
    }
    limit = int(profile.get("followup_limit") or 2)
    queries: list[dict[str, str]] = []
    seen_queries: set[str] = set()

    for slot_key in list(missing_slot_keys or [])[:limit]:
        candidates = followup_templates.get(slot_key)
        if isinstance(candidates, str):
            candidate_list = [candidates]
        else:
            candidate_list = [str(item).strip() for item in (candidates or []) if str(item).strip()]

        if not candidate_list:
            label = slot_labels.get(slot_key) or slot_key
            candidate_list = [f"{subject} {label} 官方 参数 真实体验"]

        for query in candidate_list:
            normalized_query = str(query).strip()
            if not normalized_query or normalized_query in seen_queries:
                continue
            seen_queries.add(normalized_query)
            queries.append({
                "scope": slot_key,
                "query": normalized_query,
                "slot_key": slot_key,
            })
    return queries


def get_component_required_slot_keys(
    *,
    component_types: list[str] | None,
    retrieval_profile: dict[str, Any] | None,
) -> list[str]:
    """根据当前页面计划使用的组件，推导这一轮必须补齐的事实槽位。"""
    profile = retrieval_profile or {}
    slot_labels = {
        str(key): str(value)
        for key, value in (profile.get("slot_labels") or {}).items()
    }
    allowed_slot_keys = set(slot_labels.keys())
    required: list[str] = []

    for component_type in component_types or []:
        normalized_type = str(component_type or "").strip()
        for slot_key in _COMPONENT_SLOT_REQUIREMENTS.get(normalized_type, ()):
            normalized_slot = str(slot_key or "").strip()
            if not normalized_slot or normalized_slot not in allowed_slot_keys:
                continue
            if normalized_slot not in required:
                required.append(normalized_slot)

    return required


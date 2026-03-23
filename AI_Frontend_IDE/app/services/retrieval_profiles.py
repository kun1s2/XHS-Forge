"""领域化检索 profile。

统一 research 节点的检索框架，但允许不同场景声明自己的关键字段、
查询变体和缺失字段规则，避免数码、旅行、探店都走同一套泛搜索。
"""

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

_TRAVEL_HINTS = (
    "旅行",
    "攻略",
    "城市",
    "景点",
    "一日游",
    "路线",
    "门票",
    "阿那亚",
    "周末去",
    "海边",
    "酒店",
    "民宿",
)

_STORE_HINTS = (
    "探店",
    "咖啡",
    "奶茶",
    "火锅",
    "餐厅",
    "店",
    "人均",
    "营业时间",
    "排队",
    "招牌",
)

_COMPONENT_SLOT_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "TitleBlock": (),
    "StoryText": ("core", "highlights"),
    "ProductSpecCard": ("core", "price"),
    "RadarChartBlock": ("core", "highlights"),
    "VersusCard": ("experience", "highlights"),
    "PollBlock": ("highlights",),
    "CoverSwiper": (),
    "LocationBlock": ("core", "transport", "route"),
    "WeatherPolaroid": ("atmosphere",),
    "QuoteBlock": ("highlights",),
    "TimelineBlock": ("timeline",),
}


def _normalize(text: str) -> str:
    return str(text or "").strip().lower()


def infer_retrieval_profile(*, user_query: str, entity_name: str, active_archetype: str | None) -> dict[str, Any]:
    query = _normalize(user_query)
    entity = _normalize(entity_name)
    archetype = _normalize(active_archetype or "")
    combined = f"{query} {entity}".strip()

    if archetype == "seeding" and any(token in combined for token in _DIGITAL_HINTS):
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

    if archetype == "travel" or any(token in combined for token in _TRAVEL_HINTS):
        return {
            "profile_name": "travel_guide",
            "domain": "travel_guide",
            "critical_slot_keys": ["hours", "transport", "route"],
            "slot_labels": {
                "ticket": "门票",
                "hours": "开放时间",
                "transport": "交通",
                "route": "路线建议",
                "duration": "游玩时长",
            },
            "followup_limit": 3,
            "query_variants": [
                {"scope": "official", "query": f"{entity_name} 门票 开放时间 官方"},
                {"scope": "review", "query": f"{entity_name} 游玩体验 路线 真实评价"},
                {"scope": "transport", "query": f"{entity_name} 交通 路线 地铁 打车"},
                {"scope": "duration", "query": f"{entity_name} 游玩时长 最佳时间 建议"},
            ],
            "followup_queries": {
                "ticket": [f"{entity_name} 门票 预约 价格 官方"],
                "hours": [f"{entity_name} 开放时间 闭馆时间 官方"],
                "transport": [f"{entity_name} 地铁 打车 公交 交通 建议"],
                "route": [f"{entity_name} 游览顺序 路线 推荐"],
                "duration": [f"{entity_name} 游玩时长 半天 一天 建议"],
            },
        }

    if archetype in {"gourmet", "food"} or any(token in combined for token in _STORE_HINTS):
        return {
            "profile_name": "store_review",
            "domain": "store_review",
            "critical_slot_keys": ["avg_price", "address", "signature"],
            "slot_labels": {
                "avg_price": "人均",
                "signature": "招牌",
                "hours": "营业时间",
                "address": "地址",
                "queue": "排队情况",
            },
            "followup_limit": 3,
            "query_variants": [
                {"scope": "official", "query": f"{entity_name} 地址 营业时间 人均"},
                {"scope": "review", "query": f"{entity_name} 招牌 推荐 排队 真实评价"},
                {"scope": "menu", "query": f"{entity_name} 招牌 菜单 人均"},
            ],
            "followup_queries": {
                "avg_price": [f"{entity_name} 人均 价格 菜单"],
                "signature": [f"{entity_name} 招牌 推荐 必点"],
                "hours": [f"{entity_name} 营业时间 官方 店铺信息"],
                "address": [f"{entity_name} 地址 定位 店铺信息"],
                "queue": [f"{entity_name} 排队 等位 高峰时段"],
            },
        }

    if archetype == "daily_share":
        return {
            "profile_name": "daily_story",
            "domain": "daily_story",
            "critical_slot_keys": [],
            "slot_labels": {
                "context": "场景背景",
                "timeline": "时间线",
                "atmosphere": "氛围细节",
            },
            "followup_limit": 2,
            "query_variants": [
                {"scope": "context", "query": f"{entity_name} 背景 真实细节"},
                {"scope": "review", "query": f"{entity_name} 体验 氛围 真实描述"},
            ],
            "followup_queries": {
                "context": [f"{entity_name} 背景 真实细节"],
                "timeline": [f"{entity_name} 时间线 经过 片段"],
                "atmosphere": [f"{entity_name} 氛围 光线 声音 细节"],
            },
        }

    return {
        "profile_name": "general_grounded",
        "domain": "general",
        "critical_slot_keys": ["core"],
        "slot_labels": {
            "core": "核心事实",
            "price": "价格或门槛",
            "highlights": "亮点",
        },
        "followup_limit": 2,
        "query_variants": [
            {"scope": "official", "query": f"{entity_name or user_query} 核心参数 价格 官方"},
            {"scope": "review", "query": f"{entity_name or user_query} 用户评价 真实体验"},
        ],
        "followup_queries": {
            "core": [f"{entity_name or user_query} 核心信息 官方"],
            "price": [f"{entity_name or user_query} 价格 门槛 官方"],
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

"""热点主题识别与快捷入口语义。

这层不负责检索或缓存，只负责把一个热点关键词解释成：
- 更稳定的展示标签
- 更合理的场景提示
- 更贴合主题的快捷演示 prompt

这样前端热榜、后台预热和用户主动追踪会共享同一套语义口径。
"""

from __future__ import annotations

from typing import Any


SEEDING_HINTS = (
    "mate",
    "iphone",
    "oppo",
    "vivo",
    "小米",
    "华为",
    "苹果",
    "索尼",
    "相机",
    "手机",
    "平板",
    "耳机",
    "显卡",
    "笔记本",
    "性能",
    "测评",
    "评测",
    "参数",
    "对比",
    "避雷",
    "pro",
    "ultra",
    "max",
    "汽车",
    "理想",
    "小鹏",
    "特斯拉",
)

def normalize_trend_keyword(keyword: str) -> str:
    """统一热点关键词显示文本。"""
    text = str(keyword or "").strip()
    if not text:
        return ""
    return " ".join(text.split())


def infer_trend_profile(keyword: str, *, scenario_hint: str | None = None) -> dict[str, str]:
    """根据关键词推断热点更适合落在哪条业务线。"""
    label = normalize_trend_keyword(keyword)
    lowered = label.lower()
    forced = str(scenario_hint or "").strip().lower()
    if forced == "seeding":
        scenario = forced
    elif any(token in lowered for token in SEEDING_HINTS) or any(token in label for token in SEEDING_HINTS):
        scenario = "seeding"
    else:
        scenario = "seeding"

    entity_type = "product_topic"

    return {
        "scenario_hint": scenario,
        "entity_type": entity_type,
    }


def build_trend_prompt(keyword: str, *, scenario_hint: str | None = None) -> str:
    """为热点入口生成更诚实、更贴题的快捷 prompt。"""
    label = normalize_trend_keyword(keyword)
    profile = infer_trend_profile(label, scenario_hint=scenario_hint)
    scenario = profile["scenario_hint"]
    if scenario == "seeding":
        return f"帮我生成一篇关于「{label}」的数码购买决策笔记，信息要靠谱，结论要鲜明，并优先补价格、参数、续航和图片证据。"
    return f"帮我围绕「{label}」生成一篇结构清晰、信息可靠的数码购买决策笔记。"


def build_trend_item(
    keyword: str,
    *,
    score: float = 0.0,
    scenario_hint: str | None = None,
    source: str = "organic",
    freshness: str = "unknown",
    cache_freshness: str = "miss",
    record_count: int = 0,
) -> dict[str, Any]:
    """构造前端热榜和工作台都能直接消费的正式热点对象。"""
    label = normalize_trend_keyword(keyword)
    profile = infer_trend_profile(label, scenario_hint=scenario_hint)
    return {
        "keyword": label,
        "score": round(float(score or 0.0), 2),
        "scenario_hint": profile["scenario_hint"],
        "entity_type": profile["entity_type"],
        "source": str(source or "organic"),
        "freshness": str(freshness or "unknown"),
        "cache_freshness": str(cache_freshness or "miss"),
        "record_count": int(record_count or 0),
        "recommended_prompt": build_trend_prompt(label, scenario_hint=profile["scenario_hint"]),
    }

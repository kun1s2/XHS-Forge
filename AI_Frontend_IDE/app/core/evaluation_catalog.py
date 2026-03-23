"""评估样例目录。

这里不直接执行模型推理，而是维护一套稳定的评估关注点，给
workspace 评估面板和自动化回归提供统一口径。
"""

from __future__ import annotations

from collections import Counter
from typing import Any


EVALUATION_CASES: list[dict[str, str]] = [
    {
        "id": "route_create_generation",
        "category": "route",
        "scenario": "seeding",
        "title": "创建请求应进入生成链",
        "expectation": "用户发起全新创作时，路由应稳定进入生成主链，而不是误判为局部编辑。",
    },
    {
        "id": "route_existing_canvas_edit",
        "category": "route",
        "scenario": "daily_share",
        "title": "已有画布编辑应命中编辑链",
        "expectation": "明显的保留/修改/重写类指令应优先命中 note_editor 路径。",
    },
    {
        "id": "planning_block_intents",
        "category": "planning",
        "scenario": "travel",
        "title": "planner 应输出 block intents",
        "expectation": "正式规划结果必须包含 block intents，供 outline_resolver 消费。",
    },
    {
        "id": "planning_policy_alignment",
        "category": "planning",
        "scenario": "seeding",
        "title": "planner policy 应携带主题与布局策略",
        "expectation": "theme/layout/fact/asset policy 应足够支撑下游执行层。",
    },
    {
        "id": "execution_targeted_edit",
        "category": "execution",
        "scenario": "daily_share",
        "title": "编辑执行应命中目标区块",
        "expectation": "changed blocks 与 target_block_id 应匹配，避免误改整页。",
    },
    {
        "id": "execution_builder_contract",
        "category": "execution",
        "scenario": "seeding",
        "title": "builder 应维持 contract-first",
        "expectation": "越权字段应被过滤，fallback 与 warning 应进入 trace。",
    },
    {
        "id": "rag_grounded_citations",
        "category": "rag",
        "scenario": "seeding",
        "title": "RAG 应提供 grounded citation",
        "expectation": "引用覆盖率、grounding score 和来源质量应达到可展示水平。",
    },
    {
        "id": "rag_conservative_no_hit",
        "category": "rag",
        "scenario": "travel",
        "title": "弱命中时应保守表达",
        "expectation": "无命中或命中偏弱时，应有 no-hit reason 和保守策略提示。",
    },
    {
        "id": "cache_preload_hit",
        "category": "cache",
        "scenario": "seeding",
        "title": "热点主题应优先命中 preload 缓存",
        "expectation": "高频主题应优先走 cache hit，而不是每轮都 live search。",
    },
    {
        "id": "cache_ttl_governance",
        "category": "cache",
        "scenario": "travel",
        "title": "缓存应暴露 freshness 与 TTL",
        "expectation": "缓存命中时需要明确 freshness、age、ttl 与 remaining ttl。",
    },
    {
        "id": "system_observability",
        "category": "system",
        "scenario": "daily_share",
        "title": "系统应保留 trace 与诊断摘要",
        "expectation": "turn trace、inspector summary 和 benchmark 应形成可讲述的工程闭环。",
    },
    {
        "id": "system_generation_stability",
        "category": "system",
        "scenario": "hybrid",
        "title": "混合场景下仍应稳定生成页面",
        "expectation": "多场景混合时仍应保持页面生成率、告警率和 builder 稳定性。",
    },
]


def build_evaluation_suite_summary() -> dict[str, Any]:
    """把评估目录压缩成前端可直接展示的摘要。"""
    category_counter = Counter(case["category"] for case in EVALUATION_CASES)
    scenario_counter = Counter(case["scenario"] for case in EVALUATION_CASES)
    return {
        "case_count": len(EVALUATION_CASES),
        "categories": [
            {"category": category, "count": count}
            for category, count in category_counter.items()
        ],
        "scenarios": [
            {"scenario": scenario, "count": count}
            for scenario, count in scenario_counter.items()
        ],
        "cases": EVALUATION_CASES,
    }

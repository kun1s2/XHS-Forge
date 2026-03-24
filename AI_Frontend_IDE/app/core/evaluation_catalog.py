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
        "title": "购买决策请求应进入生成主链",
        "expectation": "用户发起新的单品购买决策请求时，路由必须进入完整生成链，而不是误判为局部编辑。",
    },
    {
        "id": "route_existing_canvas_edit",
        "category": "route",
        "scenario": "seeding",
        "title": "已有决策档案编辑应命中编辑链",
        "expectation": "明显的保留/修改/补图/重写类指令应优先命中编辑链，而不是重建整页。",
    },
    {
        "id": "planning_block_intents",
        "category": "planning",
        "scenario": "seeding",
        "title": "planner 应输出数码决策容器",
        "expectation": "正式规划结果必须包含购买决策场景的 block intents，供容器层消费。",
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
        "scenario": "seeding",
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
        "id": "rag_dual_track_ingestion",
        "category": "rag",
        "scenario": "seeding",
        "title": "资料入库应同时落向量轨和结构化轨",
        "expectation": "上传资料后应既能召回 chunk，也能抽到候选知识进入待审区。",
    },
    {
        "id": "rag_session_review_gate",
        "category": "rag",
        "scenario": "seeding",
        "title": "候选知识必须先审再生成",
        "expectation": "cache/web/上传资料抽出的候选知识不能直接写成页面事实，必须先进入待审会话知识。",
    },
    {
        "id": "rag_conservative_no_hit",
        "category": "rag",
        "scenario": "seeding",
        "title": "弱命中时应保守表达",
        "expectation": "无命中或命中偏弱时，应有 no-hit reason 和保守策略提示。",
    },
    {
        "id": "agentic_knowledge_plan",
        "category": "system",
        "scenario": "seeding",
        "title": "agent 应显式给出 knowledge plan",
        "expectation": "每轮复杂任务都应能解释缺什么、先查什么、为何需要用户确认。",
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
        "scenario": "seeding",
        "title": "热点型号缓存应暴露 freshness 与 TTL",
        "expectation": "热门机型缓存命中时需要明确 freshness、age、ttl 与 remaining ttl。",
    },
    {
        "id": "system_observability",
        "category": "system",
        "scenario": "seeding",
        "title": "系统应保留 trace 与诊断摘要",
        "expectation": "turn trace、inspector summary 和 benchmark 应形成可讲述的工程闭环。",
    },
    {
        "id": "system_generation_stability",
        "category": "system",
        "scenario": "seeding",
        "title": "购买决策档案应稳定生成",
        "expectation": "数字购买决策主场景下应保持页面生成率、告警率和 builder 稳定性。",
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

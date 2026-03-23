"""工作台诊断与评估面板的展示模型构造器。

这里统一负责把运行时 state、会话快照和追踪信息压缩成 Inspector 与
Benchmark 需要的展示数据，避免 `workspace.py` 同时承担 API 路由和
复杂聚合逻辑。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from app.core.evaluation_catalog import build_evaluation_suite_summary
from app.core.note_document import build_note_document_from_state


def dedupe_assets(assets: list) -> list[dict]:
    """按 URL 去重素材，同时尽量保留更完整的元数据。"""
    deduped: dict[str, dict] = {}
    for asset in assets or []:
        if not isinstance(asset, dict):
            continue
        url = str(asset.get("url") or "").strip()
        if not url:
            continue
        existing = deduped.get(url, {})
        merged = {**existing, **asset}
        if existing.get("desc") and not asset.get("desc"):
            merged["desc"] = existing["desc"]
        deduped[url] = merged
    return list(deduped.values())


def build_inspector_summary(values: dict) -> dict:
    """构造 AgentInspector 单轮诊断面板所需的数据模型。"""
    note_document = values.get("note_document") or build_note_document_from_state(values)
    blocks = list((note_document or {}).get("blocks") or [])
    assets = dedupe_assets(list((note_document or {}).get("assets") or []) or values.get("image_assets", []) or [])
    retrieved_knowledge = values.get("retrieved_knowledge") if isinstance(values.get("retrieved_knowledge"), dict) else {}
    turn_trace = values.get("turn_trace") if isinstance(values.get("turn_trace"), dict) else {}
    note_editor_trace = turn_trace.get("note_editor") if isinstance(turn_trace.get("note_editor"), dict) else {}
    workspace_action_trace = turn_trace.get("workspace_action") if isinstance(turn_trace.get("workspace_action"), dict) else {}
    component_builder_trace = turn_trace.get("component_builder") if isinstance(turn_trace.get("component_builder"), dict) else {}
    execution_trace = note_editor_trace or workspace_action_trace
    warnings = [str(item) for item in (turn_trace.get("warnings") or []) if item]
    fact_bindings = list((note_document or {}).get("fact_bindings") or [])
    conflict_count = len(retrieved_knowledge.get("fact_conflicts") or [])
    confirmed_count = len(retrieved_knowledge.get("confirmed_facts") or {})
    source_count = len(retrieved_knowledge.get("fact_sources") or [])
    retrieval_summary = retrieved_knowledge.get("retrieval_summary") if isinstance(retrieved_knowledge.get("retrieval_summary"), dict) else {}
    retrieval_hits = [item for item in (retrieved_knowledge.get("retrieval_hits") or []) if isinstance(item, dict)]
    retrieval_eval = retrieved_knowledge.get("retrieval_eval") if isinstance(retrieved_knowledge.get("retrieval_eval"), dict) else {}
    changed_blocks = list(turn_trace.get("changed_blocks") or [])
    builder_items = [payload for payload in component_builder_trace.values() if isinstance(payload, dict)]
    builder_component_types = [str(item.get("component_type") or "") for item in builder_items if item.get("component_type")]
    builder_fallback_count = len([item for item in builder_items if item.get("fallback_used")])
    builder_contract_filter_count = sum(int(item.get("contract_filter_count") or 0) for item in builder_items)
    builder_precheck_warning_count = sum(int(item.get("precheck_warning_count") or 0) for item in builder_items)
    builder_fact_summary_count = sum(int(item.get("fact_summary_count") or 0) for item in builder_items)
    builder_asset_count = sum(int(item.get("asset_count") or 0) for item in builder_items)
    builder_prompt_modes = sorted({str(item.get("prompt_mode") or "") for item in builder_items if item.get("prompt_mode")})
    scenarios = list((note_document.get("document_meta") or {}).get("scenarios") or values.get("scenarios") or [])
    entity_name = str(retrieved_knowledge.get("entity_name") or "").strip() or "未识别主体"
    last_action = str(execution_trace.get("action") or "")
    status = "attention" if warnings or conflict_count else ("active" if blocks else "idle")

    suggestions = []
    if not blocks:
        suggestions.append("先生成一版页面，再观察结构化编辑是否命中目标。")
    if "style_changed_without_content" in warnings:
        suggestions.append("这轮更像改到了样式层，优先检查输入是否包含明确文本指令，以及命中区块是否正确。")
    if "noop" in warnings:
        suggestions.append("系统没有找到可落地的内容差异，建议检查结构化计划是否命中了正确区块。")
    if execution_trace.get("fallback_used"):
        suggestions.append("本轮进入了兜底路径，说明结构化动作还没有完全覆盖这类表达。")
    if builder_fallback_count:
        suggestions.append("这轮有组件落到了 builder fallback，建议优先检查组件 contract、事实摘要和局部业务简报。")
    if builder_contract_filter_count:
        suggestions.append("这轮 builder 过滤掉了一些越权字段，优先检查 block contract 是否与语义目标匹配。")
    if builder_precheck_warning_count:
        suggestions.append("这轮 builder 在合并前发现了必填字段缺失，建议核对简报和事实摘要是否足够支撑组件生成。")
    if builder_fact_summary_count:
        suggestions.append("builder 当前只消费压缩后的事实摘要；如果组件细节不够，优先补结构化 facts，而不是继续堆全局 prompt。")
    if conflict_count:
        suggestions.append("当前仍有待确认事实，强结论最好先在右侧确认冲突值。")
    if retrieval_summary.get("no_hit_reason"):
        suggestions.append("这轮 RAG 命中较弱，输出应偏保守，优先检查检索策略、query refinement 和引用来源。")
    if not source_count and retrieval_summary.get("live_search_used"):
        suggestions.append("这轮做了在线搜证，但没有拿到足够稳定的引用来源，建议面试展示时强调系统会保守表达。")
    if not suggestions:
        suggestions.append("当前链路状态正常，可以直接查看本轮追踪和结构化计划。")

    headline = "当前工作台状态正常"
    if status == "attention":
        headline = "这轮执行里有需要关注的信号"
    elif status == "idle":
        headline = "当前工作台还没有生成内容"
    elif last_action:
        headline = f"最近一次动作：{last_action}"

    return {
        "headline": headline,
        "status": status,
        "focus": {
            "entity_name": entity_name,
            "scenarios": scenarios,
            "selected_block_id": values.get("selected_element_id") or execution_trace.get("target_block_id") or None,
            "intent_route": values.get("intent_route") or "等待指令",
            "active_panel": values.get("active_panel") or "main",
        },
        "document": {
            "title": (note_document.get("document_meta") or {}).get("title") or "未命名页面",
            "block_count": len(blocks),
            "asset_count": len(assets),
            "fact_binding_count": len(fact_bindings),
            "theme_preset": (note_document.get("theme") or {}).get("preset") or "default",
        },
        "execution": {
            "last_action": last_action or "暂无动作",
            "target_block_id": execution_trace.get("target_block_id") or values.get("selected_element_id") or "global",
            "structured": execution_trace.get("structured", True),
            "fallback_used": bool(execution_trace.get("fallback_used")),
            "warning_count": len(warnings),
            "changed_block_count": len(changed_blocks),
            "runtime_count": len(values.get("agent_backends") or {}),
        },
        "builder": {
            "component_count": len(builder_items),
            "fallback_count": builder_fallback_count,
            "contract_filter_count": builder_contract_filter_count,
            "precheck_warning_count": builder_precheck_warning_count,
            "fact_summary_count": builder_fact_summary_count,
            "asset_count": builder_asset_count,
            "prompt_modes": builder_prompt_modes,
            "contract_first": bool(builder_items),
            "component_types": builder_component_types[:6],
        },
        "facts": {
            "confidence": str(retrieved_knowledge.get("fact_confidence") or "unknown"),
            "conflict_count": conflict_count,
            "confirmed_count": confirmed_count,
            "source_count": source_count,
            "needs_confirmation": bool(retrieved_knowledge.get("needs_fact_confirmation") or conflict_count),
        },
        "retrieval": {
            "strategy": str(retrieval_summary.get("strategy") or "none"),
            "policy_name": str(retrieval_summary.get("policy_name") or ""),
            "policy_path": str(retrieval_summary.get("policy_path") or ""),
            "ingest_mode": str(retrieval_summary.get("ingest_mode") or "none"),
            "cache_hit": bool(retrieval_summary.get("cache_hit")),
            "cache_freshness": str(retrieval_summary.get("cache_freshness") or ("fresh" if retrieval_summary.get("cache_hit") else "miss")),
            "cache_key": str(retrieval_summary.get("cache_key") or ""),
            "cache_age_seconds": int(retrieval_summary.get("cache_age_seconds") or 0),
            "cache_ttl_seconds": int(retrieval_summary.get("cache_ttl_seconds") or 0),
            "cache_remaining_ttl_seconds": int(retrieval_summary.get("cache_remaining_ttl_seconds") or 0),
            "live_search_used": bool(retrieval_summary.get("live_search_used")),
            "query": str(retrieval_summary.get("query") or ""),
            "entity_name": str(retrieval_summary.get("entity_name") or entity_name),
            "citation_count": int(retrieval_summary.get("citation_count") or source_count),
            "image_count": int(retrieval_summary.get("image_count") or len(assets)),
            "grounding_status": str(retrieval_summary.get("grounding_status") or ("grounded" if source_count else "unknown")),
            "freshness": str(retrieval_summary.get("freshness") or ("cached" if retrieval_summary.get("cache_hit") else "unknown")),
            "record_count": int(retrieval_summary.get("record_count") or 0),
            "fresh_record_count": int(retrieval_summary.get("fresh_record_count") or 0),
            "stale_record_count": int(retrieval_summary.get("stale_record_count") or 0),
            "rerank_applied": bool(retrieval_summary.get("rerank_applied")),
            "query_variants": [str(item) for item in (retrieval_summary.get("query_variants") or []) if str(item)],
            "hit_scopes": [str(item) for item in (retrieval_summary.get("hit_scopes") or []) if str(item)],
            "no_hit_reason": str(retrieval_summary.get("no_hit_reason") or ""),
            "hit_count": len(retrieval_hits),
            "citation_coverage": float(retrieval_eval.get("citation_coverage") or 0),
            "grounding_score": float(retrieval_eval.get("grounding_score") or 0),
            "source_quality": str(retrieval_eval.get("source_quality") or "unknown"),
            "recommendation": str(retrieval_eval.get("recommendation") or ""),
        },
        "assets": {
            "cover_count": len([asset for asset in assets if str(asset.get("role") or "") == "cover"]),
            "bound_asset_count": len([asset for asset in assets if asset.get("used_by_blocks")]),
        },
        "suggestions": suggestions,
    }


def _safe_float(value: Any) -> float:
    """把任意值安全转成浮点数。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    """把任意值安全转成整数。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _ratio(numerator: float, denominator: float) -> float:
    """安全计算比率，避免除零。"""
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _top_counter_rows(counter: Counter, limit: int = 6, *, key_name: str = "name") -> list[dict]:
    """把 Counter 结果转成前端更容易消费的排行列表。"""
    rows = []
    for name, count in counter.most_common(limit):
        if not name:
            continue
        rows.append({key_name: str(name), "count": int(count)})
    return rows


def _pick_row_value(row: Any, key: str, index: int = 0):
    """兼容 dict / SQL row / tuple 三种读取方式。"""
    if isinstance(row, dict):
        return row.get(key)
    if hasattr(row, "_mapping"):
        return row._mapping.get(key)
    try:
        return row[index]
    except Exception:
        return None


def build_benchmark_overview(session_snapshots: list[dict], title_resolver) -> dict:
    """把多轮会话快照聚合成 Benchmark 面板。"""
    session_count = len(session_snapshots)
    if session_count == 0:
        return {
            "generated_at": datetime.now().isoformat(),
            "session_count": 0,
            "active_document_count": 0,
            "summary": {},
            "rag": {},
            "cache": {},
            "execution": {},
            "distributions": {"scenarios": [], "components": [], "themes": [], "entities": []},
            "sessions": [],
            "recommendations": ["当前还没有可评估的会话数据，先生成几轮页面后再看 benchmark。"],
        }

    scenario_counter: Counter = Counter()
    component_counter: Counter = Counter()
    theme_counter: Counter = Counter()
    entity_counter: Counter = Counter()

    total_block_count = 0
    total_asset_count = 0
    generated_session_count = 0
    warning_session_count = 0
    total_changed_block_count = 0
    builder_component_total = 0
    builder_fallback_total = 0
    retrieval_session_count = 0
    cache_hit_count = 0
    live_search_count = 0
    rerank_count = 0
    grounded_count = 0
    citation_total = 0
    citation_coverage_total = 0.0
    grounding_score_total = 0.0
    record_total = 0
    fresh_record_total = 0
    stale_record_total = 0
    cache_fresh_count = 0
    cache_stale_count = 0
    cache_age_total = 0
    cache_age_count = 0
    ttl_remaining_total = 0
    ttl_remaining_count = 0

    sessions: list[dict] = []

    for snapshot in session_snapshots:
        values = snapshot.get("values") or {}
        thread_id = str(snapshot.get("thread_id") or "")
        title = str(snapshot.get("title") or title_resolver(values, thread_id))
        updated_at = str(snapshot.get("updated_at") or datetime.now().isoformat())
        note_document = values.get("note_document") or build_note_document_from_state(values)
        summary = snapshot.get("inspector_summary") or build_inspector_summary(values)

        blocks = [block for block in (note_document.get("blocks") or []) if isinstance(block, dict)]
        assets = dedupe_assets(list((note_document.get("assets") or []) or values.get("image_assets", []) or []))
        document = summary.get("document") if isinstance(summary.get("document"), dict) else {}
        retrieval = summary.get("retrieval") if isinstance(summary.get("retrieval"), dict) else {}
        execution = summary.get("execution") if isinstance(summary.get("execution"), dict) else {}
        builder = summary.get("builder") if isinstance(summary.get("builder"), dict) else {}
        focus = summary.get("focus") if isinstance(summary.get("focus"), dict) else {}

        block_count = len(blocks)
        asset_count = len(assets)
        total_block_count += block_count
        total_asset_count += asset_count
        total_changed_block_count += _safe_int(execution.get("changed_block_count"))
        builder_component_total += _safe_int(builder.get("component_count"))
        builder_fallback_total += _safe_int(builder.get("fallback_count"))

        if block_count:
            generated_session_count += 1
        if _safe_int(execution.get("warning_count")) > 0:
            warning_session_count += 1

        scenarios = [str(item) for item in (focus.get("scenarios") or []) if str(item)]
        for scenario in scenarios:
            scenario_counter[scenario] += 1
        for block in blocks:
            component_counter[str(block.get("type") or "Unknown")] += 1

        theme_preset = str(document.get("theme_preset") or "default")
        theme_counter[theme_preset] += 1

        entity_name = str(focus.get("entity_name") or "").strip()
        if entity_name and entity_name != "未识别主体":
            entity_counter[entity_name] += 1

        retrieval_active = any([
            _safe_int(retrieval.get("hit_count")) > 0,
            _safe_int(retrieval.get("citation_count")) > 0,
            bool(retrieval.get("cache_hit")),
            bool(retrieval.get("live_search_used")),
            _safe_int(retrieval.get("record_count")) > 0,
        ])
        if retrieval_active:
            retrieval_session_count += 1
            citation_total += _safe_int(retrieval.get("citation_count"))
            citation_coverage_total += _safe_float(retrieval.get("citation_coverage"))
            grounding_score_total += _safe_float(retrieval.get("grounding_score"))
            record_total += _safe_int(retrieval.get("record_count"))
            fresh_record_total += _safe_int(retrieval.get("fresh_record_count"))
            stale_record_total += _safe_int(retrieval.get("stale_record_count"))
            if str(retrieval.get("grounding_status") or "") == "grounded":
                grounded_count += 1
            if bool(retrieval.get("cache_hit")):
                cache_hit_count += 1
            if bool(retrieval.get("live_search_used")):
                live_search_count += 1
            if bool(retrieval.get("rerank_applied")):
                rerank_count += 1
            cache_freshness = str(retrieval.get("cache_freshness") or "")
            if cache_freshness == "fresh":
                cache_fresh_count += 1
            elif cache_freshness == "expired":
                cache_stale_count += 1
            cache_age = _safe_int(retrieval.get("cache_age_seconds"))
            cache_remaining = _safe_int(retrieval.get("cache_remaining_ttl_seconds"))
            if cache_age > 0:
                cache_age_total += cache_age
                cache_age_count += 1
            if cache_remaining > 0:
                ttl_remaining_total += cache_remaining
                ttl_remaining_count += 1

        sessions.append({
            "thread_id": thread_id,
            "title": title,
            "updated_at": updated_at,
            "block_count": block_count,
            "asset_count": asset_count,
            "scenario": scenarios[0] if scenarios else "general",
            "theme_preset": theme_preset,
            "entity_name": entity_name or "未识别主体",
            "grounding_status": str(retrieval.get("grounding_status") or "unknown"),
            "citation_count": _safe_int(retrieval.get("citation_count")),
            "cache_freshness": str(retrieval.get("cache_freshness") or "unknown"),
            "warning_count": _safe_int(execution.get("warning_count")),
        })

    rag_denominator = retrieval_session_count or 1
    recommendation_pool: list[str] = []
    cache_hit_rate = _ratio(cache_hit_count, retrieval_session_count)
    live_search_rate = _ratio(live_search_count, retrieval_session_count)
    citation_coverage_avg = _ratio(citation_coverage_total, rag_denominator)
    grounding_score_avg = _ratio(grounding_score_total, rag_denominator)
    builder_fallback_rate = _ratio(builder_fallback_total, builder_component_total or 1)
    warning_rate = _ratio(warning_session_count, session_count)

    if retrieval_session_count == 0:
        recommendation_pool.append("目前还没有足够的检索样本，先用 seeding / travel / daily_share 各跑几轮再看 benchmark。")
    if retrieval_session_count and cache_hit_rate < 0.35:
        recommendation_pool.append("缓存命中率偏低，建议继续扩 system_preload 覆盖面，优先预热高频 entity 和热点 topic。")
    if retrieval_session_count and citation_coverage_avg < 0.65:
        recommendation_pool.append("引用覆盖率偏低，建议优先补 block / field 级 citation 落点，而不是继续增加检索结果数量。")
    if retrieval_session_count and grounding_score_avg < 0.75:
        recommendation_pool.append("grounding 分数还有提升空间，建议继续优化 query refinement、source weighting 和 evidence slice。")
    if builder_component_total and builder_fallback_rate > 0.2:
        recommendation_pool.append("builder fallback 偏高，优先检查 component contract、facts summary 和 asset summary 是否足够支撑组件生成。")
    if warning_rate > 0.3:
        recommendation_pool.append("执行告警比例偏高，建议优先复盘 trace 里的 noop / fallback_used / style_changed_without_content。")
    if not recommendation_pool:
        recommendation_pool.append("当前 benchmark 指标稳定，可以直接把这张面板当成面试里的系统评估页来展示。")

    sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)

    return {
        "generated_at": datetime.now().isoformat(),
        "session_count": session_count,
        "active_document_count": generated_session_count,
        "summary": {
            "avg_block_count": round(_ratio(total_block_count, session_count), 2),
            "avg_asset_count": round(_ratio(total_asset_count, session_count), 2),
            "avg_changed_block_count": round(_ratio(total_changed_block_count, session_count), 2),
            "generated_session_rate": round(_ratio(generated_session_count, session_count), 3),
        },
        "rag": {
            "session_count": retrieval_session_count,
            "grounded_session_count": grounded_count,
            "avg_citation_count": round(_ratio(citation_total, rag_denominator), 2),
            "avg_citation_coverage": round(citation_coverage_avg, 3),
            "avg_grounding_score": round(grounding_score_avg, 3),
            "avg_record_count": round(_ratio(record_total, rag_denominator), 2),
            "avg_fresh_record_count": round(_ratio(fresh_record_total, rag_denominator), 2),
            "avg_stale_record_count": round(_ratio(stale_record_total, rag_denominator), 2),
            "grounded_session_rate": round(_ratio(grounded_count, rag_denominator), 3),
        },
        "cache": {
            "cache_hit_rate": round(cache_hit_rate, 3),
            "live_search_rate": round(live_search_rate, 3),
            "rerank_rate": round(_ratio(rerank_count, rag_denominator), 3),
            "fresh_cache_rate": round(_ratio(cache_fresh_count, rag_denominator), 3),
            "expired_cache_rate": round(_ratio(cache_stale_count, rag_denominator), 3),
            "avg_cache_age_seconds": round(_ratio(cache_age_total, cache_age_count or 1), 1),
            "avg_remaining_ttl_seconds": round(_ratio(ttl_remaining_total, ttl_remaining_count or 1), 1),
        },
        "execution": {
            "builder_component_total": builder_component_total,
            "builder_fallback_total": builder_fallback_total,
            "builder_fallback_rate": round(builder_fallback_rate, 3),
            "warning_session_count": warning_session_count,
            "warning_rate": round(warning_rate, 3),
        },
        "distributions": {
            "scenarios": _top_counter_rows(scenario_counter, key_name="scenario"),
            "components": _top_counter_rows(component_counter, key_name="component_type"),
            "themes": _top_counter_rows(theme_counter, key_name="theme_preset"),
            "entities": _top_counter_rows(entity_counter, key_name="entity_name"),
        },
        "sessions": sessions[:8],
        "recommendations": recommendation_pool[:4],
    }


def _score_to_status(score: float) -> str:
    """把 0-100 分数映射成统一状态标签。"""
    if score >= 85:
        return "strong"
    if score >= 70:
        return "healthy"
    if score >= 55:
        return "attention"
    return "weak"


def _bounded_score(value: float) -> float:
    """把任意分数收敛到 0-100。"""
    return max(0.0, min(100.0, value))


def _build_category_evaluation(
    *,
    name: str,
    score: float,
    metrics: dict[str, Any],
    summary: str,
    recommendation: str,
    case_count: int,
    covered_case_count: int,
) -> dict[str, Any]:
    """统一构造单个评估维度的展示结构。"""
    safe_score = round(_bounded_score(score), 1)
    return {
        "name": name,
        "score": safe_score,
        "status": _score_to_status(safe_score),
        "summary": summary,
        "recommendation": recommendation,
        "suite_case_count": case_count,
        "covered_case_count": covered_case_count,
        "coverage_rate": round(_ratio(covered_case_count, case_count or 1), 3),
        "metrics": metrics,
    }


def build_evaluation_overview(session_snapshots: list[dict], title_resolver) -> dict:
    """把最近一批会话聚合成正式评估面板。

    这层和 benchmark 的区别在于：benchmark 更像运行画像；evaluation 更强调
    六类核心能力是否达到“能稳定讲、能稳定回归”的水平。
    """
    suite_summary = build_evaluation_suite_summary()
    case_rows = list(suite_summary.get("cases") or [])
    category_case_counter = Counter(str(item.get("category") or "") for item in case_rows)
    scenario_case_counter = Counter(str(item.get("scenario") or "") for item in case_rows)
    session_count = len(session_snapshots)

    if session_count == 0:
        return {
            "generated_at": datetime.now().isoformat(),
            "overall_score": 0.0,
            "overall_status": "idle",
            "summary": "当前还没有可评估的会话数据。",
            "suite": {
                **suite_summary,
                "observed_scenarios": [],
                "missing_scenarios": [row["scenario"] for row in suite_summary.get("scenarios", [])],
            },
            "categories": [],
            "sessions": [],
            "recommendations": ["先生成几轮 seeding / travel / daily_share 页面，再观察评估面板。"],
        }

    route_decision_count = 0
    route_followthrough_count = 0
    fast_path_count = 0
    planner_session_count = 0
    planning_policy_count = 0
    planning_alignment_count = 0
    execution_success_count = 0
    execution_warning_free_count = 0
    execution_targeted_count = 0
    retrieval_session_count = 0
    grounded_session_count = 0
    citation_coverage_total = 0.0
    grounding_score_total = 0.0
    no_hit_guarded_count = 0
    cache_session_count = 0
    cache_hit_count = 0
    fresh_cache_count = 0
    ttl_visible_count = 0
    system_observed_count = 0
    system_generated_count = 0
    runtime_count_total = 0
    warning_session_count = 0

    sessions: list[dict[str, Any]] = []
    observed_scenarios: set[str] = set()

    for snapshot in session_snapshots:
        values = snapshot.get("values") or {}
        thread_id = str(snapshot.get("thread_id") or "")
        title = str(snapshot.get("title") or title_resolver(values, thread_id))
        updated_at = str(snapshot.get("updated_at") or datetime.now().isoformat())
        note_document = values.get("note_document") or build_note_document_from_state(values)
        summary = snapshot.get("inspector_summary") or build_inspector_summary(values)
        focus = summary.get("focus") if isinstance(summary.get("focus"), dict) else {}
        document = summary.get("document") if isinstance(summary.get("document"), dict) else {}
        execution = summary.get("execution") if isinstance(summary.get("execution"), dict) else {}
        builder = summary.get("builder") if isinstance(summary.get("builder"), dict) else {}
        retrieval = summary.get("retrieval") if isinstance(summary.get("retrieval"), dict) else {}

        intent_route = str(focus.get("intent_route") or values.get("intent_route") or "").strip()
        block_count = _safe_int(document.get("block_count") or len(note_document.get("blocks") or []))
        changed_block_count = _safe_int(execution.get("changed_block_count"))
        warning_count = _safe_int(execution.get("warning_count"))
        runtime_count = _safe_int(execution.get("runtime_count"))
        planner_output = values.get("planner_output") if isinstance(values.get("planner_output"), dict) else {}
        planner_policy = values.get("planner_policy") if isinstance(values.get("planner_policy"), dict) else {}
        block_intents = [item for item in (planner_output.get("block_intents") or []) if isinstance(item, dict)]
        theme_policy = planner_policy.get("theme_policy") if isinstance(planner_policy.get("theme_policy"), dict) else {}
        layout_policy = planner_policy.get("layout_policy") if isinstance(planner_policy.get("layout_policy"), dict) else {}
        fact_policy = planner_policy.get("fact_policy") if isinstance(planner_policy.get("fact_policy"), dict) else {}
        asset_policy = planner_policy.get("asset_policy") if isinstance(planner_policy.get("asset_policy"), dict) else {}
        scenarios = [str(item) for item in ((note_document.get("document_meta") or {}).get("scenarios") or focus.get("scenarios") or []) if str(item)]
        observed_scenarios.update(scenarios)

        if intent_route and intent_route != "等待指令":
            route_decision_count += 1
            if block_count > 0 or changed_block_count > 0 or bool(retrieval.get("live_search_used")) or bool(retrieval.get("cache_hit")):
                route_followthrough_count += 1
        if str((values.get("agent_backends") or {}).get("intent_agent") or "") == "deterministic_fast_path":
            fast_path_count += 1

        if block_intents:
            planner_session_count += 1
            if block_count > 0:
                planning_alignment_count += 1
        if any([theme_policy, layout_policy, fact_policy, asset_policy]):
            planning_policy_count += 1

        if block_count > 0 or changed_block_count > 0:
            execution_success_count += 1
        if warning_count == 0:
            execution_warning_free_count += 1
        if changed_block_count > 0 and str(execution.get("target_block_id") or "global") not in {"", "暂无动作"}:
            execution_targeted_count += 1

        retrieval_active = any([
            _safe_int(retrieval.get("citation_count")) > 0,
            _safe_int(retrieval.get("hit_count")) > 0,
            _safe_int(retrieval.get("record_count")) > 0,
            bool(retrieval.get("live_search_used")),
            bool(retrieval.get("cache_hit")),
        ])
        if retrieval_active:
            retrieval_session_count += 1
            citation_coverage_total += _safe_float(retrieval.get("citation_coverage"))
            grounding_score_total += _safe_float(retrieval.get("grounding_score"))
            if str(retrieval.get("grounding_status") or "") == "grounded":
                grounded_session_count += 1
            if str(retrieval.get("no_hit_reason") or "").strip():
                no_hit_guarded_count += 1

        cache_active = bool(retrieval.get("cache_hit")) or bool(retrieval.get("live_search_used")) or str(retrieval.get("cache_freshness") or "") not in {"", "unknown"}
        if cache_active:
            cache_session_count += 1
            if bool(retrieval.get("cache_hit")):
                cache_hit_count += 1
            if str(retrieval.get("cache_freshness") or "") == "fresh":
                fresh_cache_count += 1
            if _safe_int(retrieval.get("cache_ttl_seconds")) > 0 or _safe_int(retrieval.get("cache_remaining_ttl_seconds")) > 0:
                ttl_visible_count += 1

        if runtime_count > 0:
            system_observed_count += 1
            runtime_count_total += runtime_count
        if block_count > 0:
            system_generated_count += 1
        if warning_count > 0:
            warning_session_count += 1

        sessions.append({
            "thread_id": thread_id,
            "title": title,
            "updated_at": updated_at,
            "scenario": scenarios[0] if scenarios else "general",
            "intent_route": intent_route or "等待指令",
            "block_count": block_count,
            "changed_block_count": changed_block_count,
            "warning_count": warning_count,
            "grounding_status": str(retrieval.get("grounding_status") or "unknown"),
            "cache_freshness": str(retrieval.get("cache_freshness") or "unknown"),
        })

    route_decision_rate = _ratio(route_decision_count, session_count)
    route_followthrough_rate = _ratio(route_followthrough_count, route_decision_count or 1)
    fast_path_rate = _ratio(fast_path_count, session_count)
    route_score = _bounded_score((route_decision_rate * 0.45 + route_followthrough_rate * 0.4 + fast_path_rate * 0.15) * 100)

    planning_coverage_rate = _ratio(planner_session_count, session_count)
    planning_policy_rate = _ratio(planning_policy_count, session_count)
    planning_alignment_rate = _ratio(planning_alignment_count, planner_session_count or 1)
    planning_score = _bounded_score((planning_coverage_rate * 0.4 + planning_policy_rate * 0.25 + planning_alignment_rate * 0.35) * 100)

    execution_success_rate = _ratio(execution_success_count, session_count)
    execution_warning_free_rate = _ratio(execution_warning_free_count, session_count)
    execution_targeted_rate = _ratio(execution_targeted_count, execution_success_count or 1)
    execution_score = _bounded_score((execution_success_rate * 0.45 + execution_warning_free_rate * 0.3 + execution_targeted_rate * 0.25) * 100)

    rag_retrieval_rate = _ratio(retrieval_session_count, session_count)
    rag_citation_coverage = _ratio(citation_coverage_total, retrieval_session_count or 1)
    rag_grounding_score = _ratio(grounding_score_total, retrieval_session_count or 1)
    rag_grounded_rate = _ratio(grounded_session_count, retrieval_session_count or 1)
    rag_guard_rate = _ratio(no_hit_guarded_count, retrieval_session_count or 1)
    rag_score = _bounded_score((rag_retrieval_rate * 0.15 + rag_citation_coverage * 0.35 + rag_grounding_score * 0.35 + max(rag_grounded_rate, rag_guard_rate) * 0.15) * 100)

    cache_hit_rate = _ratio(cache_hit_count, cache_session_count or 1)
    cache_fresh_rate = _ratio(fresh_cache_count, cache_session_count or 1)
    cache_ttl_visibility_rate = _ratio(ttl_visible_count, cache_session_count or 1)
    cache_score = _bounded_score((cache_hit_rate * 0.45 + cache_fresh_rate * 0.3 + cache_ttl_visibility_rate * 0.25) * 100)

    system_generation_rate = _ratio(system_generated_count, session_count)
    system_observed_rate = _ratio(system_observed_count, session_count)
    system_warning_free_rate = _ratio(session_count - warning_session_count, session_count)
    avg_runtime_nodes = _ratio(runtime_count_total, system_observed_count or 1)
    runtime_health = min(avg_runtime_nodes / 4.0, 1.0) if avg_runtime_nodes > 0 else 0.0
    system_score = _bounded_score((system_generation_rate * 0.4 + system_observed_rate * 0.2 + system_warning_free_rate * 0.25 + runtime_health * 0.15) * 100)

    category_evaluations = [
        _build_category_evaluation(
            name="路由评估",
            score=route_score,
            metrics={
                "decision_rate": round(route_decision_rate, 3),
                "followthrough_rate": round(route_followthrough_rate, 3),
                "fast_path_rate": round(fast_path_rate, 3),
                "evaluated_session_count": session_count,
            },
            summary="看请求是否被送进正确链路，以及路由之后是否真的落到了对应执行路径。",
            recommendation=(
                "继续补强 deterministic fast-path 和编辑类 followthrough 断言。"
                if route_score < 80 else
                "当前路由链比较稳定，可以直接在面试中展示 create/edit/research 的分流能力。"
            ),
            case_count=category_case_counter["route"],
            covered_case_count=category_case_counter["route"] if route_decision_count else 0,
        ),
        _build_category_evaluation(
            name="规划评估",
            score=planning_score,
            metrics={
                "planning_coverage_rate": round(planning_coverage_rate, 3),
                "policy_presence_rate": round(planning_policy_rate, 3),
                "intent_alignment_rate": round(planning_alignment_rate, 3),
                "planner_session_count": planner_session_count,
            },
            summary="看 planner 是否稳定产出 block intents 与 policy，并能和最终文档结构对齐。",
            recommendation=(
                "优先补 planner block intents 覆盖率和 policy presence。"
                if planning_score < 80 else
                "规划层已经比较稳定，适合用来解释为什么不是所有逻辑都交给单个 agent。"
            ),
            case_count=category_case_counter["planning"],
            covered_case_count=category_case_counter["planning"] if planner_session_count else 0,
        ),
        _build_category_evaluation(
            name="执行评估",
            score=execution_score,
            metrics={
                "execution_success_rate": round(execution_success_rate, 3),
                "warning_free_rate": round(execution_warning_free_rate, 3),
                "targeted_change_rate": round(execution_targeted_rate, 3),
                "builder_component_sessions": execution_success_count,
            },
            summary="看 note_editor、builder、verifier 是否把改动准确落到目标区块与字段。",
            recommendation=(
                "优先降低 warning rate 与 builder fallback。"
                if execution_score < 80 else
                "执行层已经足够稳，可以直接展示 changed blocks / warnings / builder traces。"
            ),
            case_count=category_case_counter["execution"],
            covered_case_count=category_case_counter["execution"] if execution_success_count else 0,
        ),
        _build_category_evaluation(
            name="RAG 评估",
            score=rag_score,
            metrics={
                "retrieval_rate": round(rag_retrieval_rate, 3),
                "citation_coverage": round(rag_citation_coverage, 3),
                "grounding_score": round(rag_grounding_score, 3),
                "grounded_session_rate": round(rag_grounded_rate, 3),
                "guarded_no_hit_rate": round(rag_guard_rate, 3),
            },
            summary="看检索是否命中、citation 是否覆盖，以及 grounded/no-hit 是否可解释。",
            recommendation=(
                "优先继续补 block/field 级 citation 与 no-hit 保守策略。"
                if rag_score < 85 else
                "RAG 已经达到可展示水位，适合现场展示 query -> hit -> citation -> grounding 的完整链路。"
            ),
            case_count=category_case_counter["rag"],
            covered_case_count=category_case_counter["rag"] if retrieval_session_count else 0,
        ),
        _build_category_evaluation(
            name="缓存评估",
            score=cache_score,
            metrics={
                "cache_hit_rate": round(cache_hit_rate, 3),
                "fresh_cache_rate": round(cache_fresh_rate, 3),
                "ttl_visibility_rate": round(cache_ttl_visibility_rate, 3),
                "cache_session_count": cache_session_count,
            },
            summary="看 preload / cache 是否真的在提升速度、复用热点知识，并且暴露 freshness 与 TTL。",
            recommendation=(
                "继续扩 system_preload 覆盖面，并优先让热点实体命中 fresh cache。"
                if cache_score < 80 else
                "缓存链已经具备面试亮点，可以直接展示 cache hit、freshness 和 TTL 诊断。"
            ),
            case_count=category_case_counter["cache"],
            covered_case_count=category_case_counter["cache"] if cache_session_count else 0,
        ),
        _build_category_evaluation(
            name="系统级评估",
            score=system_score,
            metrics={
                "generation_rate": round(system_generation_rate, 3),
                "observability_rate": round(system_observed_rate, 3),
                "warning_free_rate": round(system_warning_free_rate, 3),
                "avg_runtime_nodes": round(avg_runtime_nodes, 2),
            },
            summary="看整套 agent 系统是否稳定生成、保留 trace，并具备足够好的运行画像。",
            recommendation=(
                "优先补更多固定 showcase 样例，继续提高 generation rate 与观测覆盖。"
                if system_score < 85 else
                "系统级闭环已经比较完整，适合把 Benchmark + Evaluation 一起当成工程能力展示。"
            ),
            case_count=category_case_counter["system"],
            covered_case_count=category_case_counter["system"] if system_observed_count else 0,
        ),
    ]

    overall_score = round(_ratio(sum(item["score"] for item in category_evaluations), len(category_evaluations) or 1), 1)
    overall_status = _score_to_status(overall_score)
    missing_scenarios = [
        row["scenario"]
        for row in suite_summary.get("scenarios", [])
        if row["scenario"] not in observed_scenarios
    ]
    recommendations = [
        item["recommendation"]
        for item in category_evaluations
        if item["status"] in {"attention", "weak"}
    ] or ["当前六类评估都处在健康区间，可以直接把这张面板当成面试里的系统评估页。"]

    sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)

    return {
        "generated_at": datetime.now().isoformat(),
        "overall_score": overall_score,
        "overall_status": overall_status,
        "summary": "六类评估统一覆盖路由、规划、执行、RAG、缓存与系统稳定性。",
        "suite": {
            **suite_summary,
            "observed_scenarios": sorted(observed_scenarios),
            "missing_scenarios": missing_scenarios,
        },
        "categories": category_evaluations,
        "sessions": sessions[:8],
        "recommendations": recommendations[:6],
    }


async def fetch_latest_session_snapshots(agent, title_resolver) -> list[dict]:
    """读取最近一批会话快照，供 benchmark 聚合使用。"""
    saver = agent.checkpointer
    query = """
        SELECT thread_id, MAX(checkpoint_id) as last_cid
        FROM checkpoints
        GROUP BY thread_id
        ORDER BY last_cid DESC
    """
    snapshots: list[dict] = []
    try:
        async with saver.conn.cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()
            for row in rows:
                tid = _pick_row_value(row, "thread_id", 0)
                state = await agent.aget_state({"configurable": {"thread_id": tid}})
                values = state.values or {}
                snapshots.append({
                    "thread_id": tid,
                    "updated_at": datetime.now().isoformat(),
                    "title": title_resolver(values, tid),
                    "values": values,
                })
    except Exception as e:
        print(f"Error fetching benchmark snapshots from DB: {e}")
        return []
    return snapshots

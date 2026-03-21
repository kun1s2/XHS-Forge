"""Presentation builders for workspace-facing diagnostics and benchmark views.

These helpers keep `workspace.py` focused on routing / state mutation while the
heavier aggregation logic for Inspector and Benchmark stays in one place.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from app.core.note_document import build_note_document_from_state


def dedupe_assets(assets: list) -> list[dict]:
    """Merge repeated asset entries by URL while preserving richer metadata."""
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
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _top_counter_rows(counter: Counter, limit: int = 6, *, key_name: str = "name") -> list[dict]:
    rows = []
    for name, count in counter.most_common(limit):
        if not name:
            continue
        rows.append({key_name: str(name), "count": int(count)})
    return rows


def _pick_row_value(row: Any, key: str, index: int = 0):
    if isinstance(row, dict):
        return row.get(key)
    if hasattr(row, "_mapping"):
        return row._mapping.get(key)
    try:
        return row[index]
    except Exception:
        return None


def build_benchmark_overview(session_snapshots: list[dict], title_resolver) -> dict:
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


async def fetch_latest_session_snapshots(agent, title_resolver) -> list[dict]:
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

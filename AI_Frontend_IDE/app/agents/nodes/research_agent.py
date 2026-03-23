import asyncio
from typing import List, Dict, Optional, Any
from app.agents.state import UIProjectState
from app.agents.tools_registry import TOOL_POOL
from app.agents.utils.entity_utils import normalize_entity_name
from app.core.query_heuristics import wants_image_search
from app.services.rag_ingestion import ingest_retrieved_knowledge
from app.services.rag_policy import build_query_variants_for_profile, choose_retrieval_policy, rerank_fact_sources
from app.services.rag_knowledge import evaluate_retrieval_quality
from app.services.retrieval_profiles import (
    infer_retrieval_profile,
    extract_fact_slots,
    compute_missing_fields,
    compute_missing_slot_keys,
    build_followup_query_variants,
)
from app.tools.network_search import search_network_structured_async
from app.tools.serpapi_search import search_google_images
from langchain_core.messages import AIMessage

# --- 🚀 事实哨兵 6.6：柔性取证版 ---

async def research_agent(state: UIProjectState) -> dict:
    """
    【事实哨兵 6.6】：根据意图信号按需取证，平衡效率与成本。
    """
    def _extract_user_text(message_content: Any) -> str:
        if isinstance(message_content, list):
            return "".join(
                str(part.get("text"))
                for part in message_content
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
            ).strip()
        return str(message_content or "").strip()

    def _infer_asset_mode_from_query(query: str) -> str:
        if wants_image_search(query):
            return "SEARCH"
        return "NONE"

    def _build_asset_label(name: str, query: str) -> str:
        candidate = str(name or "").strip() or str(query or "").strip()
        candidate = candidate.replace("帮我", "").replace("请", "").strip()
        for prefix in ["搜几张", "搜一下", "搜", "找几张", "找一下", "找"]:
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix):].strip()
        for suffix in ["实拍图", "图片", "配图"]:
            if candidate.endswith(suffix):
                candidate = candidate[: -len(suffix)].strip()
        return candidate or "素材"

    def _dedupe_fact_sources(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            key = url or title
            if not key:
                continue
            existing = deduped.get(key, {})
            merged = {**existing, **item}
            if existing.get("snippet") and not item.get("snippet"):
                merged["snippet"] = existing["snippet"]
            deduped[key] = merged
        return list(deduped.values())

    def _format_structured_results(scope: str, query: str, results: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        formatted_lines = []
        fact_sources = []
        for item in results[:5]:
            title = str(item.get("title") or "").strip()
            link = str(item.get("link") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if title or snippet:
                formatted_lines.append(f"- {title}: {snippet}")
            if title or link or snippet:
                fact_sources.append({
                    "title": title or "未命名来源",
                    "url": link,
                    "snippet": snippet,
                    "source_type": "web",
                    "source_scope": scope,
                    "query": query,
                })
        return "\n".join(formatted_lines), fact_sources

    main_msgs = state.get("main_messages", [])
    if not main_msgs: return {}
    user_query = _extract_user_text(main_msgs[-1].content)
    entity_name = normalize_entity_name(user_query)
    retrieval_profile = infer_retrieval_profile(
        user_query=user_query,
        entity_name=entity_name or user_query,
        active_archetype=str(state.get("active_archetype") or ""),
    )
    retrieval_policy = choose_retrieval_policy(
        user_query=user_query,
        cache_keywords=[],
        needs_assets=_infer_asset_mode_from_query(user_query),
        retrieval_profile=retrieval_profile,
    )

    # 1. 缓存嗅探
    from app.services.cache_service import cache_service
    hit_keywords = await cache_service.match_trends_in_text(user_query)
    retrieval_policy = choose_retrieval_policy(
        user_query=user_query,
        cache_keywords=hit_keywords,
        needs_assets=_infer_asset_mode_from_query(user_query),
        retrieval_profile=retrieval_profile,
    )
    if hit_keywords:
        cached = await cache_service.get_hot_knowledge(hit_keywords[0])
        if cached:
            print(f"🚀 [哨兵加速] 命中缓存: {hit_keywords[0]}")
            next_knowledge = dict(cached or {})
            kb_snapshot = await cache_service.get_knowledge_snapshot(hit_keywords[0])
            cache_snapshot = await cache_service.get_hot_knowledge_snapshot(hit_keywords[0])
            retrieval_eval = evaluate_retrieval_quality(
                retrieval_hits=next_knowledge.get("retrieval_hits") or [],
                fact_sources=next_knowledge.get("fact_sources") or [],
                knowledge_records=kb_snapshot.get("records") or [],
            )
            retrieval_summary = dict(next_knowledge.get("retrieval_summary") or {})
            retrieval_summary.update({
                "strategy": "cache_hit",
                "policy_name": retrieval_policy.get("policy_name") if 'retrieval_policy' in locals() else "cache_then_live_grounded",
                "policy_path": retrieval_policy.get("policy_path") if 'retrieval_policy' in locals() else "cache_first_then_live_search",
                "cache_hit": True,
                "live_search_used": False,
                "ingest_mode": retrieval_summary.get("ingest_mode") or "system_preload",
                "topic": hit_keywords[0],
                "query": user_query,
                "entity_name": entity_name or user_query,
                "source_count": len(next_knowledge.get("fact_sources") or []),
                "citation_count": len(next_knowledge.get("fact_sources") or []),
                "image_count": len(next_knowledge.get("image_assets") or []),
                "freshness": kb_snapshot.get("freshness") or "cached",
                "record_count": kb_snapshot.get("record_count") or 0,
                "stale_record_count": kb_snapshot.get("stale_record_count") or 0,
                "fresh_record_count": kb_snapshot.get("fresh_record_count") or 0,
                "rerank_applied": False,
                "cache_key": str(cache_snapshot.get("cache_key") or ""),
                "cache_freshness": str(cache_snapshot.get("cache_freshness") or "unknown"),
                "cache_age_seconds": int(cache_snapshot.get("age_seconds") or 0),
                "cache_ttl_seconds": int(cache_snapshot.get("ttl_seconds") or 0),
                "cache_remaining_ttl_seconds": int(cache_snapshot.get("remaining_ttl_seconds") or 0),
                "retrieval_profile": retrieval_profile.get("profile_name") or "general_grounded",
                "retrieval_domain": retrieval_profile.get("domain") or "general",
            })
            next_knowledge["retrieval_summary"] = retrieval_summary
            next_knowledge["retrieval_eval"] = retrieval_eval
            next_knowledge["knowledge_records"] = kb_snapshot.get("records") or []
            return {"retrieved_knowledge": next_knowledge, "agent_backends": {"research_agent": "deterministic_tool_orchestrator"}}

    # 2. 信号提取
    intent_v2 = state.get("intent_result_v2") or {}
    if isinstance(intent_v2, dict) and intent_v2:
        needs_assets = str(intent_v2.get("needs_assets") or "none").lower()
        asset_mode = "SEARCH" if needs_assets == "search" else "NONE"
    else:
        asset_mode = _infer_asset_mode_from_query(user_query)
    retrieval_policy = choose_retrieval_policy(
        user_query=user_query,
        cache_keywords=hit_keywords,
        needs_assets=asset_mode,
        retrieval_profile=retrieval_profile,
    )

    # 3. 并发取证决策
    search_tool = TOOL_POOL["network_search"]
    query_variants = build_query_variants_for_profile(
        user_query=user_query,
        entity_name=entity_name or user_query,
        retrieval_profile=retrieval_profile,
    )
    official_query = next((item["query"] for item in query_variants if item.get("scope") == "official"), query_variants[0]["query"])
    review_query = next((item["query"] for item in query_variants if item.get("scope") == "review"), query_variants[min(1, len(query_variants) - 1)]["query"])
    
    # 任务 A: 文本事实（这是后续页面骨架与组件填充的刚需）
    search_task_1 = search_tool.ainvoke({"query": official_query})
    search_task_2 = search_tool.ainvoke({"query": review_query})
    structured_tasks = [
        search_network_structured_async(item["query"], num=4)
        for item in query_variants
    ]
    
    # 任务 B: 图片打捞（柔性触发）
    # 只有当意图探测开启了 SEARCH 模式才启动
    should_search_images = (asset_mode == "SEARCH")
    image_query = f"{user_query} 真实素材图"
    image_task = search_google_images(query=image_query, num=5) if should_search_images else asyncio.sleep(0, result=[])

    print(f"📡 [搜证引擎] 正在作业... 文本: 并发多路强取 | 图片: {'已激活' if should_search_images else '已旁路'}")

    official_results: list[dict[str, Any]] = []
    review_results: list[dict[str, Any]] = []
    raw_web_content_1 = ""
    raw_web_content_2 = ""
    try:
        results = await asyncio.wait_for(
            asyncio.gather(search_task_1, search_task_2, *structured_tasks, image_task),
            timeout=25.0,
        )
        raw_web_content_1, raw_web_content_2, *structured_results, real_image_urls = results
        structured_results_map = {
            query_variants[idx]["scope"]: structured_results[idx]
            for idx in range(min(len(query_variants), len(structured_results)))
        }
        official_results = structured_results_map.get("official") or []
        review_results = structured_results_map.get("review") or []
        raw_web_content = f"""【官方资料】:
{raw_web_content_1}
【用户评价】:
{raw_web_content_2}"""
    except Exception as e:
        print(f"⚠️ [搜证引擎] 物理强取超时或失败: {e}，返回兜底空数据。")
        raw_web_content = "无网络数据"
        real_image_urls = []
        official_results = []
        review_results = []
        structured_results_map = {}

    # 构造虚假的 AIMessage 包含 tool_calls
    print(f"✅ [搜证完毕] 已获取真实文本与 {len(real_image_urls) if real_image_urls else 0} 条图片直链。")

    # 构造 image_assets 结构
    asset_label = _build_asset_label(entity_name, user_query)
    final_assets = [{"url": u, "desc": f"{asset_label} 实拍图"} for u in real_image_urls]
    official_summary, official_sources = _format_structured_results("official", official_query, official_results)
    review_summary, review_sources = _format_structured_results("review", review_query, review_results)
    fact_sources = _dedupe_fact_sources([*official_sources, *review_sources])
    preview_records = await ingest_retrieved_knowledge(
        entity_name=entity_name or user_query,
        scenario=str((state.get("active_archetype") or "general")),
        ingest_mode="task_triggered_ingest",
        knowledge={"fact_sources": fact_sources, "retrieval_hits": []},
    )
    fact_sources = rerank_fact_sources(fact_sources, preview_records.get("records") or [])
    retrieval_hits = []
    for item in query_variants:
        scope = item["scope"]
        results_for_scope = structured_results_map.get(scope) or []
        retrieval_hits.append({
            "scope": scope,
            "query": item["query"],
            "count": len(results_for_scope),
            "titles": [str(entry.get("title") or "").strip() for entry in results_for_scope[:4] if entry.get("title")],
        })
    slot_labels = dict(retrieval_profile.get("slot_labels") or {})
    fact_slots = extract_fact_slots(profile_name=str(retrieval_profile.get("profile_name") or ""), results_by_scope=structured_results_map)
    missing_slot_keys_before_followup = compute_missing_slot_keys(
        slot_labels=slot_labels,
        fact_slots=fact_slots,
    )
    missing_fields_before_followup = compute_missing_fields(
        slot_labels=slot_labels,
        fact_slots=fact_slots,
    )

    followup_query_variants = build_followup_query_variants(
        user_query=user_query,
        entity_name=entity_name or user_query,
        retrieval_profile=retrieval_profile,
        missing_slot_keys=missing_slot_keys_before_followup,
    )
    followup_results_map: dict[str, list[dict[str, Any]]] = {}
    followup_sources: list[dict[str, Any]] = []
    followup_sections: list[str] = []
    if followup_query_variants:
        print(f"🧩 [缺字段补搜] 首轮仍缺字段 {missing_fields_before_followup}，追加 {len(followup_query_variants)} 路定向补搜。")
        try:
            followup_batches = await asyncio.wait_for(
                asyncio.gather(*[
                    search_network_structured_async(item["query"], num=3)
                    for item in followup_query_variants
                ]),
                timeout=18.0,
            )
            for idx, item in enumerate(followup_query_variants):
                scope = str(item.get("scope") or "followup")
                results_for_scope = followup_batches[idx] or []
                if not results_for_scope:
                    continue
                followup_results_map.setdefault(scope, []).extend(results_for_scope)
                summary_text, sources = _format_structured_results(scope, item["query"], results_for_scope)
                if summary_text:
                    followup_sections.append(f"【补搜 {scope}】:\n{summary_text}")
                followup_sources.extend(sources)
        except Exception as followup_error:
            print(f"⚠️ [缺字段补搜] 第二轮补搜失败: {followup_error}")

    for scope, rows in followup_results_map.items():
        structured_results_map.setdefault(scope, [])
        structured_results_map[scope].extend(rows)

    fact_sources = rerank_fact_sources(
        _dedupe_fact_sources([*fact_sources, *followup_sources]),
        preview_records.get("records") or [],
    )
    for item in followup_query_variants:
        results_for_scope = followup_results_map.get(str(item.get("scope") or "")) or []
        retrieval_hits.append({
            "scope": str(item.get("scope") or ""),
            "query": item["query"],
            "count": len(results_for_scope),
            "titles": [str(entry.get("title") or "").strip() for entry in results_for_scope[:4] if entry.get("title")],
            "followup": True,
        })

    fact_slots = extract_fact_slots(profile_name=str(retrieval_profile.get("profile_name") or ""), results_by_scope=structured_results_map)
    missing_fields = compute_missing_fields(
        slot_labels=slot_labels,
        fact_slots=fact_slots,
    )
    retrieval_summary = {
        "strategy": "live_search_with_citations",
        "policy_name": retrieval_policy.get("policy_name") or "cache_then_live_grounded",
        "policy_path": retrieval_policy.get("policy_path") or "cache_first_then_live_search",
        "retrieval_profile": retrieval_profile.get("profile_name") or "general_grounded",
        "retrieval_domain": retrieval_profile.get("domain") or "general",
        "cache_hit": False,
        "cache_freshness": "miss",
        "cache_age_seconds": 0,
        "cache_ttl_seconds": 0,
        "cache_remaining_ttl_seconds": 0,
        "live_search_used": True,
        "ingest_mode": "task_triggered_ingest",
        "query": user_query,
        "entity_name": entity_name or user_query,
        "query_variants": [item["query"] for item in query_variants],
        "asset_mode": asset_mode.lower(),
        "image_query": image_query if should_search_images else "",
        "source_count": len(fact_sources),
        "citation_count": len(fact_sources),
        "image_count": len(final_assets),
        "hit_scopes": [hit["scope"] for hit in retrieval_hits if hit["count"]],
        "freshness": "live",
        "grounding_status": "grounded" if fact_sources else ("visual_only" if final_assets else "weak"),
        "no_hit_reason": "" if fact_sources else "本轮联网搜证没有拿到足够稳定的结构化来源，后续输出应偏保守。",
        "rerank_applied": True,
        "missing_fields": missing_fields,
        "missing_fields_before_followup": missing_fields_before_followup,
        "followup_search_used": bool(followup_query_variants),
        "followup_query_variants": [item["query"] for item in followup_query_variants],
    }
    combined_text_facts = f"""【官方资料】:
{raw_web_content_1}
{official_summary if official_summary else ""}
【用户评价】:
{raw_web_content_2}
{review_summary if review_summary else ""}
{chr(10).join(followup_sections) if followup_sections else ""}"""
    knowledge = {
        "entity_name": entity_name or user_query,
        "is_fact_ready": True,
        "battle_report": None,
        "text_facts": str(combined_text_facts),
        "fact_sources": fact_sources,
        "fact_slots": fact_slots,
        "missing_fields": missing_fields,
        "retrieval_hits": retrieval_hits,
        "retrieval_summary": retrieval_summary,
    }
    ingest_result = await ingest_retrieved_knowledge(
        entity_name=entity_name or user_query,
        scenario=str((state.get("active_archetype") or "general")),
        ingest_mode="task_triggered_ingest",
        knowledge=knowledge,
    )
    knowledge["retrieval_summary"] = {
        **retrieval_summary,
        "record_count": ingest_result["kb_snapshot"].get("record_count") or 0,
        "fresh_record_count": ingest_result["kb_snapshot"].get("fresh_record_count") or 0,
        "stale_record_count": ingest_result["kb_snapshot"].get("stale_record_count") or 0,
        "freshness": ingest_result["kb_snapshot"].get("freshness") or retrieval_summary["freshness"],
    }
    knowledge["retrieval_eval"] = ingest_result["retrieval_eval"]
    knowledge["knowledge_records"] = ingest_result["records"]

    return {
        "agent_backends": {"research_agent": "deterministic_tool_orchestrator"},
        # 直接将战术情报返回给全局状态，而不是去污染聊天记录！
        "retrieved_knowledge": {
            **knowledge,
            "text_facts": str(combined_text_facts),
        },
        "image_assets": final_assets,
        # 仅返回一条简短的系统通知
        "messages": [AIMessage(content=f"已完成对「{entity_name or user_query}」的物理搜证。")]
    }

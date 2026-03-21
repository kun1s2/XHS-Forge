import asyncio
from typing import List, Dict, Optional, Any
from app.agents.state import UIProjectState
from app.agents.tools_registry import TOOL_POOL
from app.agents.utils.entity_utils import normalize_entity_name
from app.core.query_heuristics import wants_image_search
from app.services.rag_ingestion import ingest_retrieved_knowledge
from app.services.rag_policy import build_query_variants, choose_retrieval_policy, rerank_fact_sources
from app.services.rag_knowledge import evaluate_retrieval_quality
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
    retrieval_policy = choose_retrieval_policy(
        user_query=user_query,
        cache_keywords=[],
        needs_assets=_infer_asset_mode_from_query(user_query),
    )

    # 1. 缓存嗅探
    from app.services.cache_service import cache_service
    hit_keywords = await cache_service.match_trends_in_text(user_query)
    retrieval_policy = choose_retrieval_policy(
        user_query=user_query,
        cache_keywords=hit_keywords,
        needs_assets=_infer_asset_mode_from_query(user_query),
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
    )

    # 3. 并发取证决策
    search_tool = TOOL_POOL["network_search"]
    query_variants = build_query_variants(user_query=user_query, entity_name=entity_name or user_query)
    official_query = query_variants[0]["query"]
    review_query = query_variants[1]["query"]
    
    # 任务 A: 文本事实（对于 content_node 是刚需）
    # 在这里可以拆分为两个关键词进行并发，模拟 plan-and-solve 降延迟
    # 如果失败，底层 tool 自己应该有容错，如果还想强制限制：
    search_task_1 = search_tool.ainvoke({"query": official_query})
    search_task_2 = search_tool.ainvoke({"query": review_query})
    structured_task_1 = search_network_structured_async(official_query, num=4)
    structured_task_2 = search_network_structured_async(review_query, num=4)
    
    # 任务 B: 图片打捞（柔性触发）
    # 只有当意图探测开启了 SEARCH 模式才启动
    should_search_images = (asset_mode == "SEARCH")
    image_query = f"{user_query} 真实素材图"
    image_task = search_google_images(query=image_query, num=5) if should_search_images else asyncio.sleep(0, result=[])

    print(f"📡 [搜证引擎] 正在作业... 文本: 并发多路强取 | 图片: {'已激活' if should_search_images else '已旁路'}")

    official_results: list[dict[str, Any]] = []
    review_results: list[dict[str, Any]] = []
    try:
        results = await asyncio.wait_for(
            asyncio.gather(search_task_1, search_task_2, structured_task_1, structured_task_2, image_task),
            timeout=25.0,
        )
        raw_web_content_1, raw_web_content_2, official_results, review_results, real_image_urls = results
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
    retrieval_hits = [
        {
            "scope": "official",
            "query": official_query,
            "count": len(official_results),
            "titles": [str(item.get("title") or "").strip() for item in official_results[:4] if item.get("title")],
        },
        {
            "scope": "review",
            "query": review_query,
            "count": len(review_results),
            "titles": [str(item.get("title") or "").strip() for item in review_results[:4] if item.get("title")],
        },
    ]
    retrieval_summary = {
        "strategy": "live_search_with_citations",
        "policy_name": retrieval_policy.get("policy_name") or "cache_then_live_grounded",
        "policy_path": retrieval_policy.get("policy_path") or "cache_first_then_live_search",
        "cache_hit": False,
        "cache_freshness": "miss",
        "cache_age_seconds": 0,
        "cache_ttl_seconds": 0,
        "cache_remaining_ttl_seconds": 0,
        "live_search_used": True,
        "ingest_mode": "task_triggered_ingest",
        "query": user_query,
        "entity_name": entity_name or user_query,
        "query_variants": [official_query, review_query],
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
    }
    combined_text_facts = f"""【官方资料】:
{raw_web_content_1}
{official_summary if official_summary else ""}
【用户评价】:
{raw_web_content_2}
{review_summary if review_summary else ""}"""
    knowledge = {
        "entity_name": entity_name or user_query,
        "is_fact_ready": True,
        "battle_report": None,
        "text_facts": str(combined_text_facts),
        "fact_sources": fact_sources,
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

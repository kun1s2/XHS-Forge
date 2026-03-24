import asyncio
from typing import List, Dict, Optional, Any
from app.agents.state import UIProjectState
from app.agents.tools_registry import TOOL_POOL
from app.agents.utils.entity_utils import normalize_entity_name
from app.core.query_heuristics import wants_image_search
from app.services.rag_ingestion import ingest_retrieved_knowledge
from app.services.knowledge_hub import (
    build_confirmed_facts_from_records,
    build_knowledge_plan,
    build_knowledge_records_from_structured,
    build_structured_slots_from_records,
    extract_candidate_records_from_text,
    knowledge_hub_service,
    merge_candidate_records_into_retrieved,
    query_persistent_records,
    query_session_records,
    records_from_user_provided_facts,
)
from app.services.rag_policy import build_query_variants_for_profile, choose_retrieval_policy, rerank_fact_sources
from app.services.rag_knowledge import evaluate_retrieval_quality
from app.services.rag_service import retrieve_knowledge_hits
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

    def _merge_structured_fact_sources(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            locator = item.get("evidence_locator") or {}
            sources.append({
                "title": str(item.get("source_title") or item.get("normalized_entity") or "知识条目"),
                "url": str((locator or {}).get("source_url") or ""),
                "snippet": str(item.get("summary") or item.get("value") or ""),
                "source_type": str(item.get("source_type") or "session_kb"),
                "source_scope": str(item.get("knowledge_scope") or "session"),
                "query": str(item.get("normalized_entity") or ""),
            })
        return _dedupe_fact_sources(sources)

    def _dedupe_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("normalized_entity") or ""),
                str(item.get("field_or_topic") or ""),
                str(item.get("value") or item.get("summary") or ""),
            )
            deduped[key] = item
        return list(deduped.values())

    main_msgs = state.get("main_messages", [])
    if not main_msgs:
        return {}
    latest_message = main_msgs[-1]
    raw_message_content = getattr(latest_message, "content", None)
    if raw_message_content is None and isinstance(latest_message, dict):
        raw_message_content = latest_message.get("content")
    user_query = _extract_user_text(raw_message_content)
    entity_name = normalize_entity_name(user_query)
    existing_knowledge = state.get("retrieved_knowledge") if isinstance(state.get("retrieved_knowledge"), dict) else {}
    knowledge_plan = build_knowledge_plan(state)
    required_fields = [str(item) for item in (knowledge_plan.get("required_fields") or []) if str(item).strip()]
    persistent_snapshot = await knowledge_hub_service.list_persistent_snapshot(entity_name=entity_name or user_query)
    seeded_knowledge = merge_candidate_records_into_retrieved(
        existing_knowledge,
        knowledge_plan=knowledge_plan,
        session_records=records_from_user_provided_facts(
            state.get("user_provided_facts") if isinstance(state.get("user_provided_facts"), dict) else {},
            entity_name=entity_name or user_query,
            active_archetype=str(state.get("active_archetype") or "seeding"),
        ),
        persistent_snapshot=persistent_snapshot,
    )
    structured_session_records = query_session_records(
        seeded_knowledge,
        entity_name=entity_name or user_query,
        required_fields=required_fields,
    )
    structured_persistent_records = query_persistent_records(
        persistent_snapshot,
        entity_name=entity_name or user_query,
        required_fields=required_fields,
    )
    structured_records = _dedupe_records([*structured_session_records, *structured_persistent_records])
    structured_slots = build_structured_slots_from_records(structured_records)
    structured_confirmed = build_confirmed_facts_from_records(structured_records)
    structured_fields = {
        str(item.get("field_or_topic") or "")
        for item in structured_records
        if isinstance(item, dict) and not str(item.get("field_or_topic") or "").startswith("topic::")
    }
    required_hit_count = len([field for field in required_fields if field in structured_fields])
    structured_threshold = min(max(2, int(knowledge_plan.get("knowledge_budget") or 3)), len(required_fields)) if required_fields else 2
    structured_enough = (required_fields and required_hit_count >= structured_threshold) or (not required_fields and len(structured_records) >= 2)
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

    if structured_enough:
        retrieval_summary = {
            "strategy": "structured_knowledge_first",
            "policy_name": retrieval_policy.get("policy_name") or "structured_first",
            "policy_path": "user/session/persistent_before_live_search",
            "retrieval_profile": retrieval_profile.get("profile_name") or "digital_grounded",
            "retrieval_domain": retrieval_profile.get("domain") or "general",
            "cache_hit": False,
            "live_search_used": False,
            "query": user_query,
            "entity_name": entity_name or user_query,
            "source_count": len(structured_records),
            "citation_count": len(structured_records),
            "image_count": 0,
            "freshness": "session_or_persistent",
            "grounding_status": "grounded" if structured_records else "weak",
            "missing_fields": [
                label
                for label in compute_missing_fields(
                    slot_labels=dict(knowledge_plan.get("field_labels") or {}),
                    fact_slots=structured_slots,
                )
            ],
            "record_count": len(build_knowledge_records_from_structured(structured_records)),
            "structured_hit_count": len(structured_records),
            "knowledge_budget": int(knowledge_plan.get("knowledge_budget") or 0),
        }
        next_knowledge = merge_candidate_records_into_retrieved(
            seeded_knowledge,
            knowledge_plan=knowledge_plan,
            persistent_snapshot=persistent_snapshot,
        )
        next_knowledge["fact_slots"] = {
            **(next_knowledge.get("fact_slots") or {}),
            **structured_slots,
        }
        next_knowledge["confirmed_facts"] = {
            **(next_knowledge.get("confirmed_facts") or {}),
            **structured_confirmed,
        }
        next_knowledge["fact_sources"] = _merge_structured_fact_sources(structured_records)
        next_knowledge["retrieval_summary"] = retrieval_summary
        next_knowledge["knowledge_records"] = [
            *[item for item in (next_knowledge.get("knowledge_records") or []) if isinstance(item, dict)],
            *build_knowledge_records_from_structured(structured_persistent_records),
        ]
        next_knowledge["retrieval_eval"] = evaluate_retrieval_quality(
            retrieval_hits=[],
            fact_sources=next_knowledge.get("fact_sources") or [],
            knowledge_records=next_knowledge.get("knowledge_records") or [],
        )
        return {
            "knowledge_plan": knowledge_plan,
            "retrieved_knowledge": next_knowledge,
            "agent_backends": {"research_agent": "structured_first_orchestrator"},
            "messages": [AIMessage(content=f"我先复用了当前会话和正式知识库里关于「{entity_name or user_query}」的已确认知识。")],
        }

    rag_result = await retrieve_knowledge_hits(
        user_query,
        limit=max(4, int(knowledge_plan.get("knowledge_budget") or 4)),
        metadata_filter={
            "scene_hint": str(state.get("active_archetype") or "seeding"),
            "entity_hint": entity_name or user_query,
        },
    )
    rag_hits = [item for item in (rag_result.get("hits") or []) if isinstance(item, dict)]
    if rag_hits:
        rag_fact_sources: list[dict[str, Any]] = []
        rag_sections: list[str] = []
        rag_retrieval_hits: list[dict[str, Any]] = []
        for idx, hit in enumerate(rag_hits):
            metadata = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
            content = str(hit.get("page_content") or "").strip()
            title = str(metadata.get("file_name") or metadata.get("document_id") or f"RAG 片段 {idx + 1}")
            if content:
                rag_sections.append(f"【{title}】\n{content}")
            rag_fact_sources.append({
                "title": title,
                "url": str(metadata.get("source_url") or metadata.get("source_path") or ""),
                "snippet": content[:240],
                "source_type": str(metadata.get("source_type") or "user_kb"),
                "source_scope": str(metadata.get("kb_scope") or "session"),
                "query": str(rag_result.get("refined_query") or user_query),
            })
            rag_retrieval_hits.append({
                "scope": "rag_hybrid",
                "query": str(rag_result.get("refined_query") or user_query),
                "count": len(rag_hits),
                "titles": [title],
                "mode": str(rag_result.get("mode") or "hybrid_rrf"),
            })
        rag_candidate_records = extract_candidate_records_from_text(
            title=f"{entity_name or user_query} RAG 候选知识",
            text="\n\n".join(rag_sections),
            entity_hint=entity_name or user_query,
            scene_hint=str(state.get("active_archetype") or "seeding"),
            source_type="user_kb",
        )
        next_knowledge = merge_candidate_records_into_retrieved(
            seeded_knowledge,
            knowledge_plan=knowledge_plan,
            candidate_records=rag_candidate_records,
            persistent_snapshot=persistent_snapshot,
        )
        next_knowledge["fact_sources"] = _dedupe_fact_sources(rag_fact_sources)
        next_knowledge["retrieval_hits"] = rag_retrieval_hits
        next_knowledge["retrieval_summary"] = {
            "strategy": "hybrid_rag_evidence",
            "policy_name": retrieval_policy.get("policy_name") or "structured_then_rag_then_live",
            "policy_path": "structured_first_then_hybrid_rag",
            "retrieval_profile": retrieval_profile.get("profile_name") or "digital_grounded",
            "retrieval_domain": retrieval_profile.get("domain") or "general",
            "cache_hit": False,
            "live_search_used": False,
            "query": user_query,
            "entity_name": entity_name or user_query,
            "source_count": len(rag_fact_sources),
            "citation_count": len(rag_fact_sources),
            "image_count": 0,
            "freshness": "session_or_persistent_docs",
            "grounding_status": "grounded" if rag_fact_sources else "weak",
            "record_count": len(next_knowledge.get("knowledge_records") or []),
            "candidate_record_count": len(rag_candidate_records),
            "missing_fields": [
                label
                for label in compute_missing_fields(
                    slot_labels=dict(knowledge_plan.get("field_labels") or {}),
                    fact_slots=next_knowledge.get("fact_slots") or {},
                )
            ],
            "rag_mode": str(rag_result.get("mode") or ""),
            "parsed_filter": rag_result.get("parsed_filter") or {},
            "refined_query": str(rag_result.get("refined_query") or user_query),
        }
        next_knowledge["retrieval_eval"] = evaluate_retrieval_quality(
            retrieval_hits=rag_retrieval_hits,
            fact_sources=next_knowledge.get("fact_sources") or [],
            knowledge_records=next_knowledge.get("knowledge_records") or [],
        )
        return {
            "knowledge_plan": knowledge_plan,
            "retrieved_knowledge": next_knowledge,
            "agent_backends": {"research_agent": "structured_plus_hybrid_rag"},
            "messages": [AIMessage(content=f"我先从知识库里补回了关于「{entity_name or user_query}」的证据片段，并整理成待审知识。")],
        }

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
            next_knowledge = merge_candidate_records_into_retrieved(
                dict(cached or {}),
                knowledge_plan=knowledge_plan,
                persistent_snapshot=persistent_snapshot,
            )
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
                "retrieval_profile": retrieval_profile.get("profile_name") or "digital_grounded",
                "retrieval_domain": retrieval_profile.get("domain") or "general",
            })
            next_knowledge["retrieval_summary"] = retrieval_summary
            next_knowledge["retrieval_eval"] = retrieval_eval
            next_knowledge["knowledge_records"] = kb_snapshot.get("records") or []
            return {
                "knowledge_plan": knowledge_plan,
                "retrieved_knowledge": next_knowledge,
                "agent_backends": {"research_agent": "deterministic_tool_orchestrator"},
            }

    # 2. 信号提取
    intent_decision = state.get("intent_decision") or {}
    if isinstance(intent_decision, dict) and intent_decision:
        asset_mode = "SEARCH" if bool(intent_decision.get("needs_assets")) else "NONE"
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
            asyncio.gather(search_task_1, search_task_2, *structured_tasks, image_task, return_exceptions=True),
            timeout=25.0,
        )
        raw_result_1, raw_result_2, *structured_result_items, image_result = results

        if isinstance(raw_result_1, Exception):
            print(f"⚠️ [搜证引擎] 官方文本搜证失败: {raw_result_1}")
            raw_web_content_1 = ""
        else:
            raw_web_content_1 = str(raw_result_1 or "")

        if isinstance(raw_result_2, Exception):
            print(f"⚠️ [搜证引擎] 评价文本搜证失败: {raw_result_2}")
            raw_web_content_2 = ""
        else:
            raw_web_content_2 = str(raw_result_2 or "")

        structured_results_map = {}
        for idx, structured_result in enumerate(structured_result_items[: len(query_variants)]):
            scope = query_variants[idx]["scope"]
            if isinstance(structured_result, Exception):
                print(f"⚠️ [搜证引擎] 结构化搜证失败 ({scope}): {structured_result}")
                structured_results_map[scope] = []
            else:
                structured_results_map[scope] = list(structured_result or [])

        official_results = structured_results_map.get("official") or []
        review_results = structured_results_map.get("review") or []

        if isinstance(image_result, Exception):
            print(f"⚠️ [搜证引擎] 图片搜证失败: {image_result}")
            real_image_urls = []
        else:
            real_image_urls = list(image_result or [])

        raw_web_content = f"""【官方资料】:
{raw_web_content_1}
【用户评价】:
{raw_web_content_2}"""
    except Exception as e:
        print(f"⚠️ [搜证引擎] 并发阶段整体失败: {e}，返回兜底空数据。")
        raw_web_content_1 = ""
        raw_web_content_2 = ""
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
        "retrieval_profile": retrieval_profile.get("profile_name") or "digital_grounded",
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
    candidate_records = extract_candidate_records_from_text(
        title=f"{entity_name or user_query} 搜索候选知识",
        text=combined_text_facts,
        entity_hint=entity_name or user_query,
        scene_hint=str(state.get("active_archetype") or "seeding"),
        source_type="web_search",
    )
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
    knowledge = merge_candidate_records_into_retrieved(
        merge_candidate_records_into_retrieved(
            seeded_knowledge,
            knowledge_plan=knowledge_plan,
            persistent_snapshot=persistent_snapshot,
        ),
        candidate_records=candidate_records,
        persistent_snapshot=persistent_snapshot,
    )
    knowledge.update({
        "entity_name": entity_name or user_query,
        "is_fact_ready": True,
        "battle_report": None,
        "text_facts": str(combined_text_facts),
        "fact_sources": fact_sources,
        "fact_slots": fact_slots,
        "missing_fields": missing_fields,
        "retrieval_hits": retrieval_hits,
        "retrieval_summary": {
            **retrieval_summary,
            "record_count": ingest_result["kb_snapshot"].get("record_count") or 0,
            "fresh_record_count": ingest_result["kb_snapshot"].get("fresh_record_count") or 0,
            "stale_record_count": ingest_result["kb_snapshot"].get("stale_record_count") or 0,
            "freshness": ingest_result["kb_snapshot"].get("freshness") or retrieval_summary["freshness"],
            "candidate_record_count": len(candidate_records),
        },
        "retrieval_eval": ingest_result["retrieval_eval"],
        "knowledge_records": ingest_result["records"],
    })

    return {
        "knowledge_plan": knowledge_plan,
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

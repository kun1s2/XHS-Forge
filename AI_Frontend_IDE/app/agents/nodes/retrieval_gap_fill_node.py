"""按块缺口驱动的补搜节点。

这个节点位于 planner 之后、outline_resolver 之前。
它不会重新接管主 research 链，而是只根据当前计划使用的组件类型，
检查 retrieved_knowledge 里还缺哪些关键槽位，并做一轮有边界的定向补搜。
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from app.agents.state import UIProjectState
from app.agents.utils.entity_utils import normalize_entity_name
from app.core.component_manifest import resolve_component_for_block_intent
from app.core.request_semantics import latest_user_text_from_messages
from app.services.rag_ingestion import ingest_retrieved_knowledge
from app.services.rag_knowledge import evaluate_retrieval_quality
from app.services.rag_policy import rerank_fact_sources
from app.services.retrieval_profiles import (
    build_followup_query_variants,
    compute_missing_fields,
    extract_fact_slots,
    get_component_required_slot_keys,
    infer_retrieval_profile,
)
from app.tools.network_search import search_network_structured_async


def _dedupe_fact_sources(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按标题/链接去重来源，避免补搜把同一条来源灌两次。"""
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


def _format_structured_sources(scope: str, query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把结构化搜索结果折成统一 fact_sources 格式。"""
    fact_sources: list[dict[str, Any]] = []
    for item in results[:5]:
        title = str(item.get("title") or "").strip()
        link = str(item.get("link") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        if title or link or snippet:
            fact_sources.append(
                {
                    "title": title or "未命名来源",
                    "url": link,
                    "snippet": snippet,
                    "source_type": "web",
                    "source_scope": scope,
                    "query": query,
                }
            )
    return fact_sources


def _collect_planned_component_types(state: UIProjectState, retrieval_profile: dict[str, Any]) -> list[str]:
    """根据 planner block intents 推导当前计划使用的组件类型。"""
    planner_output = state.get("planner_output") or {}
    component_types: list[str] = []
    scenario_scores = planner_output.get("scenario_scores") or {}
    has_images = bool(state.get("image_assets"))
    for item in list(planner_output.get("block_intents") or []):
        if not isinstance(item, dict):
            continue
        preferred_component = str(item.get("preferred_component") or "").strip()
        intent_type = str(item.get("intent_type") or "").strip()
        component_type = preferred_component or resolve_component_for_block_intent(
            intent_type,
            has_images=has_images,
            scenario_scores=scenario_scores,
        )
        if component_type and component_type not in component_types:
            component_types.append(component_type)
    return component_types


def _merge_slot_summaries_into_attributes(
    *,
    knowledge: dict[str, Any],
    slot_labels: dict[str, str],
    fact_slots: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """把补搜拿到的 slot summary 投影成更适合 builder 直接消费的 core_attributes。"""
    attrs = dict(knowledge.get("core_attributes") or {})
    for slot_key, slot in (fact_slots or {}).items():
        if not isinstance(slot, dict):
            continue
        summary = str(slot.get("summary") or "").strip()
        if not summary:
            continue
        label = str(slot_labels.get(str(slot_key)) or slot_key).strip()
        if not label:
            continue
        attrs[label] = summary
    return attrs


async def retrieval_gap_fill_with_limit(
    state: UIProjectState,
    *,
    followup_limit_boost: int = 0,
) -> dict[str, Any]:
    """根据当前计划使用的组件，补齐 research 仍缺失的关键字段。"""
    knowledge = deepcopy(state.get("retrieved_knowledge") or {})
    if not isinstance(knowledge, dict) or not knowledge:
        return {
            "turn_trace": {"retrieval_gap_fill": {"used": False, "reason": "missing_retrieved_knowledge"}},
            "agent_backends": {"retrieval_gap_fill": "deterministic_slot_gap_filler"},
        }

    planner_output = state.get("planner_output") or {}
    block_intents = list(planner_output.get("block_intents") or [])
    if not block_intents:
        return {
            "turn_trace": {"retrieval_gap_fill": {"used": False, "reason": "missing_planner_block_intents"}},
            "agent_backends": {"retrieval_gap_fill": "deterministic_slot_gap_filler"},
        }

    user_query = latest_user_text_from_messages(state.get("main_messages", []) or [])
    entity_name = normalize_entity_name(knowledge.get("entity_name") or user_query)
    retrieval_profile = infer_retrieval_profile(
        user_query=user_query,
        entity_name=entity_name or user_query,
        active_archetype=str(state.get("active_archetype") or ""),
    )
    if followup_limit_boost:
        retrieval_profile = {
            **retrieval_profile,
            "followup_limit": int(retrieval_profile.get("followup_limit") or 2) + int(followup_limit_boost),
        }
    slot_labels = {
        str(key): str(value)
        for key, value in (retrieval_profile.get("slot_labels") or {}).items()
    }
    critical_slot_keys = [str(key) for key in (retrieval_profile.get("critical_slot_keys") or []) if str(key)]
    if not slot_labels:
        return {
            "turn_trace": {"retrieval_gap_fill": {"used": False, "reason": "profile_has_no_slot_labels"}},
            "agent_backends": {"retrieval_gap_fill": "deterministic_slot_gap_filler"},
        }

    component_types = _collect_planned_component_types(state, retrieval_profile)
    required_slot_keys = get_component_required_slot_keys(
        component_types=component_types,
        retrieval_profile=retrieval_profile,
    )
    fact_slots = deepcopy(knowledge.get("fact_slots") or {})
    missing_slot_keys = [slot for slot in required_slot_keys if slot not in fact_slots]
    missing_fields = compute_missing_fields(slot_labels=slot_labels, fact_slots=fact_slots)
    critical_missing_fields = [slot_labels.get(slot, slot) for slot in missing_slot_keys if slot in critical_slot_keys]

    retrieval_summary = dict(knowledge.get("retrieval_summary") or {})
    if not missing_slot_keys:
        retrieval_summary.update(
            {
                "retrieval_profile": retrieval_profile.get("profile_name") or "digital_grounded",
                "retrieval_domain": retrieval_profile.get("domain") or "digital_review",
                "block_required_fields": [slot_labels.get(slot, slot) for slot in required_slot_keys],
                "block_gap_fill_used": False,
                "critical_missing_fields": [],
            }
        )
        knowledge["retrieval_summary"] = retrieval_summary
        knowledge["missing_fields"] = missing_fields
        return {
            "retrieved_knowledge": knowledge,
            "turn_trace": {
                "retrieval_gap_fill": {
                    "used": False,
                    "component_types": component_types,
                    "required_slot_keys": required_slot_keys,
                    "missing_slot_keys": [],
                    "missing_fields": missing_fields,
                    "critical_missing_fields": [],
                }
            },
            "agent_backends": {"retrieval_gap_fill": "deterministic_slot_gap_filler"},
        }

    followup_query_variants = build_followup_query_variants(
        user_query=user_query,
        entity_name=entity_name or user_query,
        retrieval_profile=retrieval_profile,
        missing_slot_keys=missing_slot_keys,
    )
    if not followup_query_variants:
        retrieval_summary.update(
            {
                "retrieval_profile": retrieval_profile.get("profile_name") or "digital_grounded",
                "retrieval_domain": retrieval_profile.get("domain") or "digital_review",
                "block_required_fields": [slot_labels.get(slot, slot) for slot in required_slot_keys],
                "block_gap_fill_used": False,
                "critical_missing_fields": critical_missing_fields,
            }
        )
        knowledge["retrieval_summary"] = retrieval_summary
        knowledge["missing_fields"] = missing_fields
        return {
            "retrieved_knowledge": knowledge,
            "turn_trace": {
                "retrieval_gap_fill": {
                    "used": False,
                    "reason": "no_followup_queries",
                    "component_types": component_types,
                    "required_slot_keys": required_slot_keys,
                    "missing_slot_keys": missing_slot_keys,
                    "missing_fields": missing_fields,
                    "critical_missing_fields": critical_missing_fields,
                }
            },
            "agent_backends": {"retrieval_gap_fill": "deterministic_slot_gap_filler"},
        }

    followup_results_map: dict[str, list[dict[str, Any]]] = {}
    followup_sources: list[dict[str, Any]] = []
    try:
        batches = await asyncio.wait_for(
            asyncio.gather(*[
                search_network_structured_async(item["query"], num=3)
                for item in followup_query_variants
            ]),
            timeout=18.0,
        )
        for idx, item in enumerate(followup_query_variants):
            scope = str(item.get("scope") or "followup")
            rows = batches[idx] or []
            if not rows:
                continue
            followup_results_map.setdefault(scope, []).extend(rows)
            followup_sources.extend(_format_structured_sources(scope, item["query"], rows))
    except Exception as followup_error:
        print(f"⚠️ [按块补搜] 第二轮补搜失败: {followup_error}")

    new_fact_slots = extract_fact_slots(
        profile_name=str(retrieval_profile.get("profile_name") or ""),
        results_by_scope=followup_results_map,
    )
    merged_fact_slots = {**fact_slots, **new_fact_slots}
    merged_fact_sources = rerank_fact_sources(
        _dedupe_fact_sources([*(knowledge.get("fact_sources") or []), *followup_sources]),
        knowledge.get("knowledge_records") or [],
    )
    merged_hits = list(knowledge.get("retrieval_hits") or [])
    for item in followup_query_variants:
        scope = str(item.get("scope") or "")
        rows = followup_results_map.get(scope) or []
        merged_hits.append(
            {
                "scope": scope,
                "query": item["query"],
                "count": len(rows),
                "titles": [str(entry.get("title") or "").strip() for entry in rows[:4] if entry.get("title")],
                "followup": True,
                "block_gap_fill": True,
            }
        )

    merged_missing_fields = compute_missing_fields(slot_labels=slot_labels, fact_slots=merged_fact_slots)
    next_knowledge = {
        **knowledge,
        "fact_slots": merged_fact_slots,
        "fact_sources": merged_fact_sources,
        "retrieval_hits": merged_hits,
        "missing_fields": merged_missing_fields,
        "core_attributes": _merge_slot_summaries_into_attributes(
            knowledge=knowledge,
            slot_labels=slot_labels,
            fact_slots=merged_fact_slots,
        ),
    }

    ingest_result = await ingest_retrieved_knowledge(
        entity_name=entity_name or user_query,
        scenario=str(state.get("active_archetype") or "general"),
        ingest_mode="task_triggered_ingest",
        knowledge={
            "fact_sources": next_knowledge.get("fact_sources") or [],
            "retrieval_hits": next_knowledge.get("retrieval_hits") or [],
        },
    )

    next_knowledge["retrieval_eval"] = evaluate_retrieval_quality(
        retrieval_hits=next_knowledge.get("retrieval_hits") or [],
        fact_sources=next_knowledge.get("fact_sources") or [],
        knowledge_records=ingest_result.get("records") or [],
    )
    next_knowledge["knowledge_records"] = ingest_result.get("records") or []
    next_knowledge["retrieval_summary"] = {
        **retrieval_summary,
        "retrieval_profile": retrieval_profile.get("profile_name") or "digital_grounded",
        "retrieval_domain": retrieval_profile.get("domain") or "general",
        "block_required_fields": [slot_labels.get(slot, slot) for slot in required_slot_keys],
        "block_gap_fill_used": bool(new_fact_slots),
        "block_gap_fill_missing_before": [slot_labels.get(slot, slot) for slot in missing_slot_keys],
        "block_gap_fill_missing_after": merged_missing_fields,
        "critical_missing_fields": [slot_labels.get(slot, slot) for slot in missing_slot_keys if slot in critical_slot_keys],
        "block_gap_fill_queries": [item["query"] for item in followup_query_variants],
        "source_count": len(next_knowledge.get("fact_sources") or []),
        "citation_count": len(next_knowledge.get("fact_sources") or []),
        "record_count": ingest_result.get("kb_snapshot", {}).get("record_count") or 0,
        "fresh_record_count": ingest_result.get("kb_snapshot", {}).get("fresh_record_count") or 0,
        "stale_record_count": ingest_result.get("kb_snapshot", {}).get("stale_record_count") or 0,
        "freshness": ingest_result.get("kb_snapshot", {}).get("freshness")
        or retrieval_summary.get("freshness")
        or "live",
    }

    return {
        "retrieved_knowledge": next_knowledge,
        "turn_trace": {
            "retrieval_gap_fill": {
                "used": bool(new_fact_slots),
                "component_types": component_types,
                "required_slot_keys": required_slot_keys,
                "missing_slot_keys": missing_slot_keys,
                "missing_fields": merged_missing_fields,
                "critical_missing_fields": [slot_labels.get(slot, slot) for slot in missing_slot_keys if slot in critical_slot_keys],
                "followup_query_variants": [item["query"] for item in followup_query_variants],
            }
        },
        "agent_backends": {"retrieval_gap_fill": "deterministic_slot_gap_filler"},
    }


async def retrieval_gap_fill_node(state: UIProjectState) -> dict[str, Any]:
    return await retrieval_gap_fill_with_limit(state)

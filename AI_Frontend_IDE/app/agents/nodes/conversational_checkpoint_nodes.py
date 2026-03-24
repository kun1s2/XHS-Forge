"""聊天流内的高频协作 checkpoint 节点。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from app.agents.nodes.retrieval_gap_fill_node import retrieval_gap_fill_with_limit
from app.agents.state import UIProjectState
from app.agents.utils.entity_utils import normalize_entity_name
from app.core.request_semantics import latest_user_text_from_messages
from app.services.conversational_checkpoints import (
    _append_custom_note,
    apply_asset_checkpoint_decision,
    apply_cautious_fact_strategy,
    apply_confirmed_only_strategy,
    apply_fact_conflict_checkpoint_decision,
    apply_knowledge_review_checkpoint_decision,
    apply_structure_checkpoint_decision,
    apply_truth_mode_checkpoint_decision,
    build_asset_checkpoint,
    build_fact_conflict_checkpoint,
    build_fact_gap_checkpoint,
    build_knowledge_review_checkpoint,
    build_structure_checkpoint,
    build_truth_mode_checkpoint,
)
from app.tools.serpapi_search import search_google_images


def _normalize_decision(raw: Any, expected_action_type: str) -> dict[str, Any]:
    if isinstance(raw, dict):
        payload = dict(raw)
    else:
        payload = {"decision": raw}
    payload.setdefault("action_type", expected_action_type)
    return payload


def _asset_search_query(state: UIProjectState) -> str:
    knowledge = state.get("retrieved_knowledge") or {}
    entity_name = normalize_entity_name((knowledge or {}).get("entity_name") or "")
    user_query = latest_user_text_from_messages(state.get("main_messages", []) or [])
    topic = entity_name or user_query or "当前主题"
    return f"{topic} 真实素材图"


async def _search_cover_assets_for_state(state: UIProjectState) -> dict[str, Any]:
    query = _asset_search_query(state)
    image_urls = await search_google_images(query=query, num=5)
    assets = deepcopy(state.get("image_assets") or [])
    seen_urls = {
        str(asset.get("url") or "").strip()
        for asset in assets
        if isinstance(asset, dict) and str(asset.get("url") or "").strip()
    }
    next_assets = []
    for index, url in enumerate(image_urls):
        normalized = str(url or "").strip()
        if not normalized or normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        next_assets.append(
            {
                "url": normalized,
                "desc": f"{query} 搜索结果",
                "source_type": "search",
                "query": query,
                "role": "cover" if index == 0 else "supporting",
                "selection_state": "selected",
            }
        )

    if not next_assets:
        fallback = apply_asset_checkpoint_decision(state, {"decision": "continue_without_images"})
        turn_trace = dict((fallback.get("turn_trace") or {}).get("conversation_checkpoints") or {})
        turn_trace["asset"] = {
            "resolved": True,
            "selected": "search_images_for_cover",
            "image_query": query,
            "image_count": 0,
            "fallback": "continue_without_images",
        }
        fallback["turn_trace"] = {"conversation_checkpoints": turn_trace}
        return fallback

    return {
        "image_assets": [{"__replace__": True}, *assets, *next_assets],
        "turn_trace": {
            "conversation_checkpoints": {
                "asset": {
                    "resolved": True,
                    "selected": "search_images_for_cover",
                    "image_query": query,
                    "image_count": len(next_assets),
                }
            }
        },
    }


async def structure_checkpoint_node(state: UIProjectState) -> dict[str, Any]:
    """强制在创建早期做一次结构协商。"""
    checkpoint = build_structure_checkpoint(state)
    if not checkpoint:
        return {}
    decision = _normalize_decision(interrupt(checkpoint), "structure_checkpoint")
    return apply_structure_checkpoint_decision(state, decision)


async def truth_mode_checkpoint_node(state: UIProjectState) -> dict[str, Any]:
    """高风险真实性确认卡。"""
    checkpoint = build_truth_mode_checkpoint(state)
    if not checkpoint:
        return {}
    decision = _normalize_decision(interrupt(checkpoint), "truth_mode_checkpoint")
    result = apply_truth_mode_checkpoint_decision(state, decision)
    if str(decision.get("decision") or "") == "provide_user_facts" and not (decision.get("user_provided_facts") or {}):
        result["main_messages"] = [
            AIMessage(content="请直接在下一条消息补充关键时间、地点、真实经过或原话，我会据此继续整理，不再假装已经掌握这些事实。")
        ]
    return result


async def fact_gap_checkpoint_node(state: UIProjectState) -> dict[str, Any]:
    """关键事实缺口确认卡。"""
    checkpoint = build_fact_gap_checkpoint(state)
    if not checkpoint:
        return {}
    decision = _normalize_decision(interrupt(checkpoint), "fact_gap_checkpoint")
    decision_value = str(decision.get("decision") or "")
    custom_note = str(decision.get("custom_note") or "").strip()
    if decision_value == "continue_research":
        gap_fill_result = await retrieval_gap_fill_with_limit(state, followup_limit_boost=2)
        trace = _append_custom_note({
            "conversation_checkpoints": {
                "fact_gap": {"resolved": True, "selected": "continue_research"}
            }
        }, note=custom_note)
        gap_fill_result["turn_trace"] = {
            **(gap_fill_result.get("turn_trace") or {}),
            **trace,
        }
        return gap_fill_result
    if decision_value == "confirmed_only":
        return apply_confirmed_only_strategy(state, custom_note=custom_note)
    return apply_cautious_fact_strategy(state, custom_note=custom_note)


async def knowledge_review_checkpoint_node(state: UIProjectState) -> dict[str, Any]:
    """搜索/缓存候选知识的人审卡。"""
    checkpoint = build_knowledge_review_checkpoint(state)
    if not checkpoint:
        return {}
    decision = _normalize_decision(interrupt(checkpoint), "knowledge_review_checkpoint")
    return apply_knowledge_review_checkpoint_decision(state, decision)


async def asset_checkpoint_node(state: UIProjectState) -> dict[str, Any]:
    """素材决策卡。"""
    checkpoint = build_asset_checkpoint(state)
    if not checkpoint:
        return {}
    decision = _normalize_decision(interrupt(checkpoint), "asset_checkpoint")
    if str(decision.get("decision") or "") == "search_images_for_cover":
        return await _search_cover_assets_for_state(state)
    return apply_asset_checkpoint_decision(state, decision)


async def fact_conflict_checkpoint_node(state: UIProjectState) -> dict[str, Any]:
    """事实冲突确认卡。"""
    checkpoint = build_fact_conflict_checkpoint(state)
    if not checkpoint:
        return {}
    decision = _normalize_decision(interrupt(checkpoint), "fact_conflict_checkpoint")
    return apply_fact_conflict_checkpoint_decision(state, decision)

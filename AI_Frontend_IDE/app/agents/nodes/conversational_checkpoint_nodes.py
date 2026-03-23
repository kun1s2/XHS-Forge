"""聊天流内的高频协作 checkpoint 节点。"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.agents.nodes.retrieval_gap_fill_node import retrieval_gap_fill_with_limit
from app.agents.state import UIProjectState
from app.services.conversational_checkpoints import (
    apply_asset_checkpoint_decision,
    apply_cautious_fact_strategy,
    apply_confirmed_only_strategy,
    apply_fact_conflict_checkpoint_decision,
    apply_structure_checkpoint_decision,
    build_asset_checkpoint,
    build_fact_conflict_checkpoint,
    build_fact_gap_checkpoint,
    build_structure_checkpoint,
)


def _normalize_decision(raw: Any, expected_action_type: str) -> dict[str, Any]:
    if isinstance(raw, dict):
        payload = dict(raw)
    else:
        payload = {"decision": raw}
    payload.setdefault("action_type", expected_action_type)
    return payload


async def structure_checkpoint_node(state: UIProjectState) -> dict[str, Any]:
    """强制在创建早期做一次结构协商。"""
    checkpoint = build_structure_checkpoint(state)
    if not checkpoint:
        return {}
    decision = _normalize_decision(interrupt(checkpoint), "structure_checkpoint")
    return apply_structure_checkpoint_decision(state, decision)


async def fact_gap_checkpoint_node(state: UIProjectState) -> dict[str, Any]:
    """关键事实缺口确认卡。"""
    checkpoint = build_fact_gap_checkpoint(state)
    if not checkpoint:
        return {}
    decision = _normalize_decision(interrupt(checkpoint), "fact_gap_checkpoint")
    decision_value = str(decision.get("decision") or "")
    if decision_value == "continue_research":
        gap_fill_result = await retrieval_gap_fill_with_limit(state, followup_limit_boost=2)
        trace = {
            "conversation_checkpoints": {
                "fact_gap": {"resolved": True, "selected": "continue_research"}
            }
        }
        gap_fill_result["turn_trace"] = {
            **(gap_fill_result.get("turn_trace") or {}),
            **trace,
        }
        return gap_fill_result
    if decision_value == "confirmed_only":
        return apply_confirmed_only_strategy(state)
    return apply_cautious_fact_strategy(state)


async def asset_checkpoint_node(state: UIProjectState) -> dict[str, Any]:
    """素材决策卡。"""
    checkpoint = build_asset_checkpoint(state)
    if not checkpoint:
        return {}
    decision = _normalize_decision(interrupt(checkpoint), "asset_checkpoint")
    return apply_asset_checkpoint_decision(state, decision)


async def fact_conflict_checkpoint_node(state: UIProjectState) -> dict[str, Any]:
    """事实冲突确认卡。"""
    checkpoint = build_fact_conflict_checkpoint(state)
    if not checkpoint:
        return {}
    decision = _normalize_decision(interrupt(checkpoint), "fact_conflict_checkpoint")
    return apply_fact_conflict_checkpoint_decision(state, decision)

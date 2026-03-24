from typing import Any

from app.agents.state import UIProjectState
from app.core.component_manifest import (
    resolve_component_candidates_for_block_intent,
    resolve_component_for_block_intent,
)
from app.core.note_document import build_note_document_from_state
from app.core.prompt_engineering import build_prompt_snapshot
from app.core.request_semantics import latest_user_text_from_messages, state_requests_create
from app.services.scenario_manager import scenario_manager


def _is_create_request(state: UIProjectState) -> bool:
    """判断当前请求是否属于需要重建页面骨架的全新创建。"""
    return state_requests_create(state)


def _latest_user_text(state: UIProjectState) -> str:
    return latest_user_text_from_messages(state.get("main_messages", []) or [])


def _build_scenario_scores(state: UIProjectState) -> dict[str, float]:
    return {"seeding": 1.0}


def _build_policy_bundle(scenario_scores: dict[str, float]) -> dict[str, Any]:
    primary = "seeding"
    config = scenario_manager.get_config(primary) or {}
    visual = config.get("visual_preference") or {}
    allowed_tools = list(config.get("allowed_tools") or config.get("tools_whitelist") or [])
    deduped_intents = [
        "hero_media",
        "decision_summary",
        "fact_list",
        "comparison",
        "risk_boundary",
        "narrative_text",
    ]
    return {
        "primary_scenario": primary,
        "tone_policy": {"bias": "sharp"},
        "layout_policy": {"preferred_block_intents": deduped_intents},
        "asset_policy": {"mode": "search_first", "allowed_tools": sorted(set(allowed_tools))},
        "fact_policy": {"prefer_confirmed_facts": True, "fallback_to_cautious_copy": True},
        "theme_policy": {"preset": str(visual.get("variant") or "digital_decision_editorial"), "interaction_bias": "high"},
    }


def _build_block_intents(state: UIProjectState, scenario_scores: dict[str, float], planner_policy: dict[str, Any]) -> list[dict[str, Any]]:
    note_document = build_note_document_from_state(state)
    if list((note_document or {}).get("blocks") or []) and not _is_create_request(state):
        return []

    knowledge = state.get("retrieved_knowledge") or {}
    has_images = bool(state.get("image_assets"))
    has_controversy = bool(state.get("has_controversy"))
    user_query = _latest_user_text(state)
    preferred = list((((planner_policy.get("layout_policy") or {}).get("preferred_block_intents")) or []))
    ranked_scenarios = sorted(scenario_scores.items(), key=lambda item: item[1], reverse=True)
    primary = ranked_scenarios[0][0] if ranked_scenarios else "seeding"
    wants_visual_cover = has_images or any(token in user_query for token in ["封面", "首图", "头图", "大图", "图片", "配图", "海报", "图文"])
    slot_map = knowledge.get("fact_slots") if isinstance(knowledge.get("fact_slots"), dict) else {}

    def _has_any_query_token(*tokens: str) -> bool:
        return any(token in user_query for token in tokens)

    def _has_slot(*keys: str) -> bool:
        return any(str(key) in slot_map for key in keys)

    intent_types = ["heading", "narrative_text"]
    if wants_visual_cover:
        intent_types.insert(0, "hero_media")
    intent_types = [intent for intent in intent_types if intent not in {"narrative_text"}]
    if _has_any_query_token("值不值得", "怎么买", "适合谁", "怎么买更稳", "结论", "先说结论", "推荐吗"):
        intent_types.append("decision_summary")
    if knowledge.get("core_attributes") or knowledge.get("confirmed_facts") or _has_any_query_token("参数", "配置", "规格", "价格", "预算", "套餐", "值不值得", "怎么买"):
        intent_types.append("fact_list")
    if knowledge.get("battle_report") or _has_any_query_token("对比", "区别", "优缺点", "更适合", "怎么选", "pk", "vs", "竞品"):
        intent_types.append("comparison")
    if _has_any_query_token("预算边界", "缺点", "注意", "不适合", "风险", "边界"):
        intent_types.append("risk_boundary")
    intent_types.append("narrative_text")
    if has_controversy or _has_any_query_token("投票", "站队", "你选", "更喜欢"):
        intent_types.append("interactive_opinion")
    if primary == "seeding" and "fact_list" not in intent_types and (knowledge.get("core_attributes") or knowledge.get("confirmed_facts")):
        intent_types.append("fact_list")
    if knowledge.get("battle_report"):
        if "comparison" not in intent_types:
            intent_types.append("comparison")
    if has_controversy or "投票" in user_query or "站队" in user_query:
        if "interactive_opinion" not in intent_types:
            intent_types.append("interactive_opinion")

    for intent_type in preferred:
        if intent_type == "hero_media" and not wants_visual_cover:
            continue
        if intent_type not in intent_types:
            intent_types.append(intent_type)

    resolved = []
    seen = set()
    for order, intent_type in enumerate(intent_types):
        if intent_type in seen:
            continue
        seen.add(intent_type)
        recommended_component = resolve_component_for_block_intent(
            intent_type,
            has_images=has_images,
            scenario_scores=scenario_scores,
        )
        candidate_components = resolve_component_candidates_for_block_intent(
            intent_type,
            has_images=has_images,
            scenario_scores=scenario_scores,
            user_query=user_query,
            active_archetype=primary,
            retrieved_knowledge=knowledge,
            preferred_component=recommended_component,
        )
        resolved.append({
            "intent_type": intent_type,
            "priority": order,
            "goal": intent_type.replace("_", " "),
            "preferred_component": recommended_component,
            "candidate_components": candidate_components,
            "selection_mode": "flexible" if candidate_components and candidate_components[0] != recommended_component else "anchored",
            "required": intent_type in {"heading", "narrative_text", "decision_summary"},
        })
    return resolved


def _build_planner_prompt_snapshot(
    state: UIProjectState,
    scenario_scores: dict[str, float],
    planner_policy: dict[str, Any],
    block_intents: list[dict[str, Any]],
) -> dict[str, Any]:
    user_query = _latest_user_text(state) or "请规划当前页面策略"
    return build_prompt_snapshot(
        "planner_agent",
        system_prompt="Digital Purchase Planner: 根据数码购买决策任务、事实状态、资产状态和组件 manifest 输出页面策略。",
        user_prompt=(
            f"user_query={user_query}\n"
            f"scenario_scores={scenario_scores}\n"
            f"has_images={bool(state.get('image_assets'))}\n"
            f"has_controversy={bool(state.get('has_controversy'))}\n"
            f"knowledge_ready={bool(state.get('retrieved_knowledge'))}"
        ),
        assistant_payload={
            "theme_policy": planner_policy.get("theme_policy", {}),
            "layout_policy": planner_policy.get("layout_policy", {}),
            "block_intents": [item.get("intent_type") for item in block_intents],
        },
    )


async def planner_node(state: UIProjectState) -> dict[str, Any]:
    scenario_scores = _build_scenario_scores(state)
    planner_policy = _build_policy_bundle(scenario_scores)
    block_intents = _build_block_intents(state, scenario_scores, planner_policy)
    planner_output = {
        "reason": "已根据混合场景、事实状态与资产状态生成页面策略",
        "scenario_scores": scenario_scores,
        "tone_policy": planner_policy.get("tone_policy", {}),
        "layout_policy": planner_policy.get("layout_policy", {}),
        "asset_policy": planner_policy.get("asset_policy", {}),
        "fact_policy": planner_policy.get("fact_policy", {}),
        "theme_policy": planner_policy.get("theme_policy", {}),
        "block_intents": block_intents,
    }
    ranked = sorted(scenario_scores.items(), key=lambda item: item[1], reverse=True)
    active_archetype = ranked[0][0] if ranked else state.get("active_archetype", "seeding")
    prompt_snapshot = _build_planner_prompt_snapshot(state, scenario_scores, planner_policy, block_intents)
    return {
        "planner_output": planner_output,
        "node_prompts": prompt_snapshot,
        "planner_policy": planner_policy,
        "scenario_scores": scenario_scores,
        "active_archetype": active_archetype,
        "scenarios": [scenario for scenario, _ in ranked] or ["seeding"],
        "turn_trace": {
            "planner": {
                "top_scenarios": ranked[:3],
                "block_intents": [item.get("intent_type") for item in block_intents],
                "theme_preset": planner_policy.get("theme_policy", {}).get("preset"),
            }
        },
        "agent_backends": {"planner": "deterministic_policy_builder"},
    }

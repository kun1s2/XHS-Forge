from typing import Any

from app.agents.state import UIProjectState
from app.core.component_manifest import resolve_component_for_block_intent
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
    intent_v2 = state.get("intent_result_v2") or {}
    raw_scores = intent_v2.get("scenario_scores") if isinstance(intent_v2, dict) else None
    if isinstance(raw_scores, dict) and raw_scores:
        return {str(key): max(0.0, min(1.0, float(value))) for key, value in raw_scores.items()}

    scenarios = list(state.get("scenarios") or [])
    active = state.get("active_archetype") or "general"
    if not scenarios:
        scenarios = [active]
    normalized = []
    for item in scenarios:
        scenario_id = str(item or "").strip() or "general"
        if scenario_id not in normalized:
            normalized.append(scenario_id)
    if active not in normalized:
        normalized.insert(0, active)
    if not normalized:
        normalized = ["general"]

    primary_weight = 0.7 if len(normalized) > 1 else 1.0
    remaining = max(0.0, 1.0 - primary_weight)
    scores = {normalized[0]: primary_weight}
    if len(normalized) > 1:
        tail_weight = remaining / (len(normalized) - 1)
        for scenario_id in normalized[1:]:
            scores[scenario_id] = tail_weight
    return scores


def _build_policy_bundle(scenario_scores: dict[str, float]) -> dict[str, Any]:
    ranked = sorted(scenario_scores.items(), key=lambda item: item[1], reverse=True)
    primary = ranked[0][0] if ranked else "general"
    preferred_block_intents = []
    allowed_tools = []
    tone_bias = "balanced"
    asset_policy = "reuse_first"
    theme_preset = f"{primary}_editorial"
    interaction_bias = "medium"

    for scenario_id, score in ranked:
        config = scenario_manager.get_config(scenario_id) or {}
        visual = config.get("visual_preference") or {}
        allowed_tools.extend(config.get("allowed_tools") or config.get("tools_whitelist") or [])
        contract = config.get("contract") or {}
        if scenario_id == primary:
            theme_preset = str(visual.get("variant") or theme_preset)
        if scenario_id == "seeding":
            tone_bias = "sharp" if score >= 0.35 else tone_bias
            asset_policy = "search_first"
            interaction_bias = "high"
            preferred_block_intents.extend(["hero_media", "evidence_summary", "comparison", "interactive_opinion"])
        elif scenario_id == "travel":
            tone_bias = "observational" if score >= 0.35 else tone_bias
            asset_policy = "search_plus_upload"
            preferred_block_intents.extend(["hero_media", "location_info", "narrative_text", "ambience_snapshot"])
        elif scenario_id == "daily_share":
            if tone_bias == "balanced":
                tone_bias = "personal"
            asset_policy = "upload_plus_generate" if asset_policy == "reuse_first" else asset_policy
            preferred_block_intents.extend(["heading", "narrative_text", "ambience_snapshot", "interactive_opinion"])
        elif scenario_id == "general":
            preferred_block_intents.extend(["heading", "narrative_text"])

        if contract.get("suggested_order"):
            for item in contract.get("suggested_order") or []:
                mapped = {
                    "TitleBlock": "heading",
                    "StoryText": "narrative_text",
                    "CoverSwiper": "hero_media",
                    "LocationBlock": "location_info",
                    "WeatherPolaroid": "ambience_snapshot"
                }.get(str(item), None)
                if mapped:
                    preferred_block_intents.append(mapped)

    deduped_intents = []
    for intent_type in preferred_block_intents:
        if intent_type not in deduped_intents:
            deduped_intents.append(intent_type)

    return {
        "primary_scenario": primary,
        "tone_policy": {"bias": tone_bias},
        "layout_policy": {"preferred_block_intents": deduped_intents or ["heading", "narrative_text"]},
        "asset_policy": {"mode": asset_policy, "allowed_tools": sorted(set(allowed_tools))},
        "fact_policy": {"prefer_confirmed_facts": True, "fallback_to_cautious_copy": True},
        "theme_policy": {"preset": theme_preset, "interaction_bias": interaction_bias},
    }


def _build_block_intents(state: UIProjectState, scenario_scores: dict[str, float], planner_policy: dict[str, Any]) -> list[dict[str, Any]]:
    note_document = build_note_document_from_state(state)
    if list((note_document or {}).get("blocks") or []) and not _is_create_request(state):
        return []

    knowledge = state.get("retrieved_knowledge") or {}
    has_images = bool(state.get("image_assets"))
    has_controversy = bool(state.get("has_controversy"))
    user_query = _latest_user_text(state)
    wants_visual_cover = has_images or any(token in user_query for token in ["封面", "首图", "头图", "大图", "图片", "配图", "海报", "图文"])
    preferred = list((((planner_policy.get("layout_policy") or {}).get("preferred_block_intents")) or []))
    ranked_scenarios = sorted(scenario_scores.items(), key=lambda item: item[1], reverse=True)
    primary = ranked_scenarios[0][0] if ranked_scenarios else "general"

    intent_types = ["heading", "narrative_text"]
    if wants_visual_cover:
        intent_types.insert(0, "hero_media")
    if primary == "travel":
        intent_types.append("location_info")
    if primary == "daily_share":
        intent_types.append("ambience_snapshot")
    if primary == "seeding" or (knowledge.get("core_attributes") or knowledge.get("confirmed_facts")):
        intent_types.append("evidence_summary")
    if knowledge.get("battle_report"):
        intent_types.append("comparison")
    if has_controversy or "投票" in user_query or "站队" in user_query:
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
        resolved_component = resolve_component_for_block_intent(
            intent_type,
            has_images=has_images,
            scenario_scores=scenario_scores,
        )
        resolved.append({
            "intent_type": intent_type,
            "priority": order,
            "goal": intent_type.replace("_", " "),
            "preferred_component": resolved_component,
            "required": intent_type in {"heading", "narrative_text"},
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
        system_prompt="Planner V2: 根据混合场景、事实状态、资产状态和组件 manifest 输出页面策略，不直接自由生成页面。",
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
    active_archetype = ranked[0][0] if ranked else state.get("active_archetype", "general")
    prompt_snapshot = _build_planner_prompt_snapshot(state, scenario_scores, planner_policy, block_intents)
    return {
        "planner_output": planner_output,
        "node_prompts": prompt_snapshot,
        "planner_policy": planner_policy,
        "scenario_scores": scenario_scores,
        "active_archetype": active_archetype,
        "scenarios": [scenario for scenario, _ in ranked] or ["general"],
        "turn_trace": {
            "planner": {
                "top_scenarios": ranked[:3],
                "block_intents": [item.get("intent_type") for item in block_intents],
                "theme_preset": planner_policy.get("theme_policy", {}).get("preset"),
            }
        },
        "agent_backends": {"planner": "deterministic_policy_builder"},
    }

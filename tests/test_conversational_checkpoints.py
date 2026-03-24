from __future__ import annotations

import pytest

from app.api.chat import _normalize_checkpoint_action_payload
from app.agents.nodes import conversational_checkpoint_nodes
from app.services.conversational_checkpoints import (
    apply_cautious_fact_strategy,
    apply_confirmed_only_strategy,
    apply_fact_conflict_checkpoint_decision,
    apply_structure_checkpoint_decision,
    apply_truth_mode_checkpoint_decision,
    build_asset_checkpoint,
    build_fact_gap_checkpoint,
    build_structure_checkpoint,
    build_truth_mode_checkpoint,
)


def _base_state() -> dict:
    return {
        "active_archetype": "seeding",
        "main_messages": [],
        "planner_output": {
            "scenario_scores": {"seeding": 1.0},
            "block_intents": [
                {"intent_type": "heading", "preferred_component": "TitleBlock"},
                {"intent_type": "narrative_text", "preferred_component": "StoryText"},
            ],
        },
        "planner_policy": {
            "layout_policy": {"preferred_block_intents": ["heading", "narrative_text"]},
            "fact_policy": {"prefer_confirmed_facts": True, "fallback_to_cautious_copy": True},
        },
        "selected_element_id": "无 (全局修改)",
        "active_panel": "main",
    }


def test_build_structure_checkpoint_for_create_request():
    state = {
        **_base_state(),
        "intent_decision": {"task_type": "create"},
    }
    payload = build_structure_checkpoint(state)
    assert payload is not None
    assert payload["action_type"] == "structure_checkpoint"
    assert len(payload["options"]) >= 2
    assert any(item["value"] == "seeding_compare" for item in payload["options"])


def test_build_truth_mode_checkpoint_for_real_diary_request():
    state = {
        **_base_state(),
        "active_archetype": "travel",
        "intent_decision": {"task_type": "create"},
        "main_messages": [{"content": "帮我整理成今天去金町湾的游玩日记，精确到几点几分"}],
    }
    payload = build_truth_mode_checkpoint(state)
    assert payload is not None
    assert payload["action_type"] == "truth_mode_checkpoint"
    assert payload["input_schema"]["submit_label"] == "按这些真实信息继续"
    option_values = [item["value"] for item in payload["options"]]
    assert "provide_user_facts" in option_values
    assert "recommended" in option_values
    fields = payload["input_schema"]["fields"]
    field_types = {item["id"]: item.get("type") for item in fields}
    assert any(value == "single_select" for value in field_types.values())
    assert any(value == "multi_select" for value in field_types.values())
    assert any(item.get("allow_custom") for item in fields)
    assert "time_precision" in field_types
    assert "schedule_slots" in field_types


def test_build_truth_mode_checkpoint_for_quote_request_uses_quote_fields():
    state = {
        **_base_state(),
        "active_archetype": "daily",
        "intent_decision": {"task_type": "create"},
        "main_messages": [{"content": "把我在海边说的原话写进去，尽量保留原话语气"}],
    }
    payload = build_truth_mode_checkpoint(state)
    assert payload is not None
    fields = payload["input_schema"]["fields"]
    field_ids = {item["id"] for item in fields}
    assert "speaker_role" in field_ids
    assert "quote_style" in field_ids
    assert "quote_context" in field_ids


def test_build_truth_mode_checkpoint_for_precise_schedule_request_uses_schedule_fields():
    state = {
        **_base_state(),
        "active_archetype": "travel",
        "intent_decision": {"task_type": "create"},
        "main_messages": [{"content": "帮我写成几点几分都清楚的真实行程"}],
    }
    payload = build_truth_mode_checkpoint(state)
    assert payload is not None
    fields = payload["input_schema"]["fields"]
    field_ids = {item["id"] for item in fields}
    assert "time_precision" in field_ids
    assert "schedule_slots" in field_ids
    schedule_field = next(item for item in fields if item["id"] == "schedule_slots")
    assert schedule_field["type"] == "multi_select"
    assert schedule_field.get("allow_custom") is True


def test_apply_truth_mode_checkpoint_decision_marks_waiting_for_user_facts():
    state = {
        **_base_state(),
        "active_archetype": "travel",
        "main_messages": [{"content": "帮我整理成今天去金町湾的游玩日记"}],
    }
    result = apply_truth_mode_checkpoint_decision(state, {"decision": "provide_user_facts"})
    assert result["checkpoint_progress"]["truth_mode"]["awaiting_user_facts"] is True
    assert result["turn_trace"]["conversation_checkpoints"]["truth_mode"]["selected"] == "provide_user_facts"


def test_apply_truth_mode_checkpoint_decision_accepts_inline_user_facts():
    state = {
        **_base_state(),
        "active_archetype": "travel",
        "main_messages": [{"content": "帮我整理成今天去金町湾的游玩日记"}],
    }
    result = apply_truth_mode_checkpoint_decision(
        state,
        {
            "decision": "provide_user_facts",
            "user_provided_facts": {
                "time_context": "上午9点到金町湾",
                "event_context": "风很大但很舒服",
            },
        },
    )
    assert result["checkpoint_progress"]["truth_mode"]["awaiting_user_facts"] is False
    assert result["user_provided_facts"]["raw_text"]
    assert result["representation_preferences"]["timeline"] == "user_provided"


def test_apply_truth_mode_checkpoint_decision_accepts_dynamic_choice_facts():
    state = {
        **_base_state(),
        "active_archetype": "travel",
        "main_messages": [{"content": "帮我整理成今天去金町湾的游玩日记"}],
    }
    result = apply_truth_mode_checkpoint_decision(
        state,
        {
            "decision": "provide_user_facts",
            "user_provided_facts": {
                "time_precision": "大概时间",
                "visited_spots": ["金町湾", "海边餐厅"],
                "focus_points": ["风景氛围", "餐饮体验"],
                "visited_spots_custom": "日落观景台",
            },
        },
    )
    assert result["checkpoint_progress"]["truth_mode"]["awaiting_user_facts"] is False
    facts = result["user_provided_facts"]
    assert facts["visited_spots"] == ["金町湾", "海边餐厅"]
    assert "日落观景台" in facts["raw_text"]
    assert result["representation_preferences"]["timeline"] == "user_provided"


def test_apply_structure_checkpoint_decision_rewrites_block_intents():
    state = {
        **_base_state(),
        "intent_decision": {"task_type": "create"},
    }
    result = apply_structure_checkpoint_decision(state, {"decision": "seeding_compare"})
    block_intents = result["planner_output"]["block_intents"]
    assert block_intents[0]["intent_type"] in {"heading", "hero_media"}
    assert any(item["intent_type"] == "comparison" for item in block_intents)
    assert all("candidate_components" in item for item in block_intents)
    assert all("selection_mode" in item for item in block_intents)
    assert result["planner_policy"]["layout_policy"]["confirmed_structure_mode"] == "seeding_compare"


def test_build_fact_gap_checkpoint_uses_critical_missing_fields():
    state = {
        **_base_state(),
        "main_messages": [{"content": "帮我做一篇华为 Mate 60 对比测评"}],
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "fact_slots": {"display": {"summary": "屏幕素质不错"}},
        },
    }
    payload = build_fact_gap_checkpoint(state)
    assert payload is not None
    assert payload["action_type"] == "fact_gap_checkpoint"
    assert "CPU / SoC" in payload["summary"]
    assert payload["proposal_summary"]
    assert payload["recommended_reason"]
    assert payload["other_allowed"] is True


def test_apply_fact_gap_strategies_preserve_custom_note():
    state = {
        **_base_state(),
        "main_messages": [{"content": "帮我做一篇华为 Mate 60 对比测评"}],
    }
    cautious = apply_cautious_fact_strategy(state, custom_note="如果补不齐，就先保守一点")
    confirmed = apply_confirmed_only_strategy(state, custom_note="只保留站得住的事实")
    assert cautious["turn_trace"]["conversation_checkpoints"]["fact_gap"]["custom_note"] == "如果补不齐，就先保守一点"
    assert confirmed["turn_trace"]["conversation_checkpoints"]["fact_gap"]["custom_note"] == "只保留站得住的事实"


def test_build_asset_checkpoint_for_multiple_assets():
    state = {
        **_base_state(),
        "image_assets": [
            {"url": "https://img.example/cover.jpg", "desc": "封面图", "role": "cover"},
            {"url": "https://img.example/detail.jpg", "desc": "细节图"},
            {"url": "https://img.example/life.jpg", "desc": "生活方式图"},
        ],
        "planner_output": {
            "scenario_scores": {"seeding": 1.0},
            "block_intents": [{"intent_type": "hero_media", "preferred_component": "CoverSwiper"}],
        },
    }
    payload = build_asset_checkpoint(state)
    assert payload is not None
    assert payload["action_type"] == "asset_checkpoint"
    option_values = [item["value"] for item in payload["options"]]
    assert "use_recommended_bundle" in option_values
    assert any(value.startswith("set_cover::") for value in option_values)


def test_build_asset_checkpoint_for_missing_images_offers_search_path():
    state = {
        **_base_state(),
        "planner_output": {
            "scenario_scores": {"seeding": 1.0},
            "block_intents": [{"intent_type": "hero_media", "preferred_component": "CoverSwiper"}],
        },
    }
    payload = build_asset_checkpoint(state)
    assert payload is not None
    option_values = [item["value"] for item in payload["options"]]
    assert "search_images_for_cover" in option_values
    assert "continue_without_images" in option_values


@pytest.mark.asyncio
async def test_asset_checkpoint_search_decision_adds_assets(monkeypatch):
    state = {
        **_base_state(),
        "main_messages": [{"content": "写一篇红米K40的测评"}],
        "retrieved_knowledge": {"entity_name": "红米K40"},
    }

    async def _fake_search_google_images(query: str, num: int = 5):
        assert "红米K40" in query
        return [
            "https://img.example/k40-cover.jpg",
            "https://img.example/k40-detail.jpg",
        ]

    monkeypatch.setattr(conversational_checkpoint_nodes, "search_google_images", _fake_search_google_images)
    result = await conversational_checkpoint_nodes._search_cover_assets_for_state(state)
    assets = result["image_assets"][1:]
    assert len(assets) == 2
    assert assets[0]["role"] == "cover"
    assert result["turn_trace"]["conversation_checkpoints"]["asset"]["selected"] == "search_images_for_cover"


def test_apply_fact_conflict_checkpoint_decision_confirms_value():
    state = {
        **_base_state(),
        "retrieved_knowledge": {
            "fact_conflicts": [
                {
                    "field": "price",
                    "values": [
                        {"value": "5499元", "sources": ["官方商城"]},
                        {"value": "5999元", "sources": ["媒体评测"]},
                    ],
                }
            ],
            "confirmed_facts": {},
            "core_attributes": {},
        },
    }
    result = apply_fact_conflict_checkpoint_decision(state, {"decision": "confirm::price::5499元"})
    confirmed = result["retrieved_knowledge"]["confirmed_facts"]
    assert confirmed["price"]["value"] == "5499元"
    assert result["retrieved_knowledge"]["needs_fact_confirmation"] is False


def test_chat_interrupt_payload_is_normalized_to_structured_action():
    payload = _normalize_checkpoint_action_payload(
        {
            "action_type": "structure_checkpoint",
            "checkpoint_id": "structure::seeding",
            "title": "先确定方向",
            "summary": "给出两套结构",
            "recommended_option": "seeding_compare",
            "blocking": True,
            "options": [
                {
                    "label": "更像对比测评",
                    "value": "seeding_compare",
                    "description": "先讲结论再讲对比",
                    "recommended": True,
                }
            ],
        }
    )
    assert payload is not None
    assert payload["action_type"] == "structure_checkpoint"
    assert payload["checkpoint_id"] == "structure::seeding"
    assert payload["options"][0]["recommended"] is True

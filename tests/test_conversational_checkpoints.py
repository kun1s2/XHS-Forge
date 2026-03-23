from __future__ import annotations

from app.api.chat import _normalize_checkpoint_action_payload
from app.services.conversational_checkpoints import (
    apply_fact_conflict_checkpoint_decision,
    apply_structure_checkpoint_decision,
    build_asset_checkpoint,
    build_fact_gap_checkpoint,
    build_structure_checkpoint,
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
        "intent_result_v2": {"task_type": "create"},
    }
    payload = build_structure_checkpoint(state)
    assert payload is not None
    assert payload["action_type"] == "structure_checkpoint"
    assert len(payload["options"]) >= 2
    assert any(item["value"] == "seeding_compare" for item in payload["options"])


def test_apply_structure_checkpoint_decision_rewrites_block_intents():
    state = {
        **_base_state(),
        "intent_result_v2": {"task_type": "create"},
    }
    result = apply_structure_checkpoint_decision(state, {"decision": "seeding_compare"})
    block_intents = result["planner_output"]["block_intents"]
    assert block_intents[0]["intent_type"] in {"heading", "hero_media"}
    assert any(item["intent_type"] == "comparison" for item in block_intents)
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

from __future__ import annotations

from app.api.chat import _normalize_checkpoint_action_payload
from app.services.conversational_checkpoints import (
    apply_asset_checkpoint_decision,
    apply_fact_gap_checkpoint_decision,
    apply_fact_conflict_checkpoint_decision,
    apply_knowledge_review_checkpoint_decision,
    apply_structure_checkpoint_decision,
    build_asset_checkpoint,
    build_fact_gap_checkpoint,
    build_fact_conflict_checkpoint,
    build_knowledge_review_checkpoint,
    build_structure_checkpoint,
)


def _base_state() -> dict:
    return {
        "active_archetype": "seeding",
        "main_messages": [],
        "planner_output": {
            "scenario_scores": {"seeding": 1.0},
            "block_intents": [],
        },
        "planner_policy": {
            "layout_policy": {"preferred_block_intents": ["decision_summary", "fact_list"]},
            "fact_policy": {"prefer_confirmed_facts": True, "fallback_to_cautious_copy": True},
        },
        "selected_element_id": "无 (全局修改)",
        "active_panel": "main",
    }


def test_build_structure_checkpoint_for_digital_create_request():
    payload = build_structure_checkpoint({**_base_state(), "intent_decision": {"task_type": "create"}})
    assert payload is not None
    assert payload["action_type"] == "structure_checkpoint"
    assert len(payload["options"]) >= 2


def test_build_fact_gap_checkpoint_for_digital_missing_fields():
    state = {
        **_base_state(),
        "main_messages": [{"content": "帮我做一篇华为 Mate 60 的购买决策档案"}],
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "fact_slots": {"display": {"summary": "屏幕素质不错"}},
        },
    }
    payload = build_fact_gap_checkpoint(state)
    assert payload is not None
    assert payload["action_type"] == "fact_gap_checkpoint"
    assert payload["recommended_reason"]


def test_build_fact_gap_checkpoint_is_skipped_for_asset_edit_on_existing_artifact():
    state = {
        **_base_state(),
        "main_messages": [{"content": "这份档案图片太少了，补几张更像真机质感的图片。"}],
        "intent_decision": {
            "task_type": "edit",
            "operation_type": "asset_edit",
            "needs_assets": True,
        },
        "note_document": {
            "document_meta": {"title": "华为 Mate 60 购买决策档案"},
            "blocks": [{"id": "title_1", "type": "TitleBlock", "props": {"title": "华为 Mate 60"}}],
        },
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "fact_slots": {"display": {"summary": "屏幕素质不错"}},
        },
    }
    assert build_fact_gap_checkpoint(state) is None


def test_build_asset_checkpoint_for_multiple_images():
    state = {
        **_base_state(),
        "image_assets": [
            {"url": "https://img.example/cover.jpg", "desc": "封面图", "role": "cover"},
            {"url": "https://img.example/detail.jpg", "desc": "细节图"},
        ],
        "planner_output": {
            "scenario_scores": {"seeding": 1.0},
            "block_intents": [{"intent_type": "hero_media", "preferred_component": "CoverSwiper"}],
        },
    }
    payload = build_asset_checkpoint(state)
    assert payload is not None
    assert payload["action_type"] == "asset_checkpoint"


def test_build_knowledge_review_checkpoint_from_candidate_records():
    state = {
        **_base_state(),
        "intent_decision": {"task_type": "create"},
        "retrieved_knowledge": {
            "candidate_session_kb": {
                "records": [
                    {
                        "normalized_entity": "华为 Mate 60",
                        "field_or_topic": "price",
                        "summary": "官方起售价 5499 元",
                        "review_status": "pending_review",
                    }
                ]
            }
        },
    }
    payload = build_knowledge_review_checkpoint(state)
    assert payload is not None
    assert payload["action_type"] == "knowledge_review_checkpoint"
    assert payload["signature"]


def test_fact_conflict_resolution_accepts_selected_value():
    state = {
        **_base_state(),
        "intent_decision": {"task_type": "create"},
        "retrieved_knowledge": {
            "fact_conflicts": [
                {
                    "field": "price",
                    "entity_name": "华为 Mate 60",
                    "values": [
                        {"value": "5499", "sources": ["官方商城"]},
                        {"value": "5999", "sources": ["电商页面"]},
                    ],
                }
            ]
        },
    }
    payload = build_fact_conflict_checkpoint(state)
    assert payload is not None
    patch = apply_fact_conflict_checkpoint_decision(state, {"decision": "confirm::price::5499"})
    assert patch["turn_trace"]["conversation_checkpoints"]["fact_conflict"]["resolved"] is True
    assert patch["checkpoint_progress"]["fact_conflict"]["resolved"] is True


def test_structure_checkpoint_decision_updates_layout_policy():
    patch = apply_structure_checkpoint_decision({**_base_state(), "intent_decision": {"task_type": "create"}}, {"decision": "seeding_compare"})
    assert patch["planner_policy"]["layout_policy"]["confirmed_structure_mode"] == "seeding_compare"
    assert patch["checkpoint_progress"]["structure"]["resolved"] is True


def test_build_structure_checkpoint_is_suppressed_after_resolution():
    state = {
        **_base_state(),
        "intent_decision": {"task_type": "create"},
        "planner_policy": {
            "layout_policy": {
                "preferred_block_intents": ["decision_summary", "fact_list"],
                "confirmed_structure_mode": "seeding_compare",
            }
        },
        "checkpoint_progress": {
            "structure": {
                "resolved": True,
                "selected": "seeding_compare",
            }
        },
    }
    payload = build_structure_checkpoint(state)
    assert payload is None


def test_checkpoint_payload_normalization_preserves_resume_token():
    payload = _normalize_checkpoint_action_payload(
        {
            "checkpoint_type": "knowledge_review_checkpoint",
            "title": "确认知识",
            "summary": "请先确认这一轮候选知识",
            "options": [{"label": "采用推荐项", "value": "approve_recommended"}],
            "resume_token": "thread:resume",
        }
    )
    assert payload is not None
    assert payload["checkpoint_type"] == "knowledge_review_checkpoint"
    assert payload["resume_token"] == "thread:resume"


def test_build_knowledge_review_checkpoint_is_suppressed_after_resolution():
    state = {
        **_base_state(),
        "intent_decision": {"task_type": "create"},
        "retrieved_knowledge": {
            "candidate_session_kb": {
                "records": [
                    {
                        "record_id": "record_price",
                        "normalized_entity": "华为 Mate 60",
                        "field_or_topic": "price",
                        "summary": "官方起售价 5499 元",
                        "review_status": "pending_review",
                    }
                ]
            }
        },
    }
    payload = build_knowledge_review_checkpoint(state)
    assert payload is not None
    patch = apply_knowledge_review_checkpoint_decision(state, {"decision": "continue_with_existing"})
    next_state = {**state, **patch}
    assert build_knowledge_review_checkpoint(next_state) is None


def test_build_fact_gap_checkpoint_is_suppressed_after_resolution():
    state = {
        **_base_state(),
        "main_messages": [{"content": "帮我做一篇华为 Mate 60 的购买决策档案"}],
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "fact_slots": {"display": {"summary": "屏幕素质不错"}},
        },
    }
    payload = build_fact_gap_checkpoint(state)
    assert payload is not None
    patch = apply_fact_gap_checkpoint_decision(state, {"decision": "continue_research"})
    next_state = {**state, **patch}
    assert build_fact_gap_checkpoint(next_state) is None


def test_build_asset_checkpoint_is_suppressed_after_resolution():
    state = {
        **_base_state(),
        "image_assets": [
            {"url": "https://img.example/cover.jpg", "desc": "封面图", "role": "cover"},
            {"url": "https://img.example/detail.jpg", "desc": "细节图"},
        ],
        "planner_output": {
            "scenario_scores": {"seeding": 1.0},
            "block_intents": [{"intent_type": "hero_media", "preferred_component": "CoverSwiper"}],
        },
    }
    payload = build_asset_checkpoint(state)
    assert payload is not None
    patch = apply_asset_checkpoint_decision(
        state,
        {
            "decision": "use_recommended_bundle",
            "asset_url": "https://img.example/cover.jpg",
            "selected_asset_ids": ["https://img.example/cover.jpg", "https://img.example/detail.jpg"],
        },
    )
    next_state = {**state, **patch}
    assert build_asset_checkpoint(next_state) is None


def test_apply_asset_checkpoint_search_images_marks_progress():
    state = {
        **_base_state(),
        "planner_output": {
            "scenario_scores": {"seeding": 1.0},
            "block_intents": [{"intent_type": "hero_media", "preferred_component": "CoverSwiper"}],
        },
    }
    patch = apply_asset_checkpoint_decision(state, {"decision": "search_images_for_cover"})
    assert patch["checkpoint_progress"]["asset"]["resolved"] is True
    assert patch["checkpoint_progress"]["asset"]["selected"] == "search_images_for_cover"


def test_build_fact_conflict_checkpoint_is_suppressed_after_resolution():
    state = {
        **_base_state(),
        "intent_decision": {"task_type": "create"},
        "retrieved_knowledge": {
            "fact_conflicts": [
                {
                    "field": "price",
                    "entity_name": "华为 Mate 60",
                    "values": [
                        {"value": "5499", "sources": ["官方商城"]},
                        {"value": "5999", "sources": ["电商页面"]},
                    ],
                }
            ]
        },
    }
    payload = build_fact_conflict_checkpoint(state)
    assert payload is not None
    patch = apply_fact_conflict_checkpoint_decision(state, {"decision": "keep_cautious"})
    next_state = {**state, **patch}
    assert build_fact_conflict_checkpoint(next_state) is None

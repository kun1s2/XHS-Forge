from app.agents.services.artifact_service import build_artifact_patch
from app.agents.services.revision_service import (
    build_revision_plan,
    build_revision_result,
    build_revision_status,
    select_primary_recipe,
)


def _base_state():
    return {
        "note_document": {
            "document_meta": {"title": "Mate 60 购买决策档案"},
            "blocks": [
                {"id": "title_1", "type": "TitleBlock", "props": {"title": "Mate 60 值不值得买"}},
                {"id": "story_1", "type": "StoryText", "props": {"paragraphs": ["第一版正文"]}},
            ],
            "assets": [],
        },
        "retrieved_knowledge": {
            "session_kb": {"knowledge_version": "session-kb::3"},
            "entity_name": "Mate 60",
        },
        "turn_trace": {
            "changed_blocks": [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}],
        },
        "critique_feedback": {
            "suggestions": ["开头可以更直接一点"],
            "action_recipes": [
                {
                    "label": "按优先建议继续优化",
                    "scope": "priority",
                    "prompt": "按优先建议继续优化当前页面",
                    "why_now": "开头结论还不够直接",
                    "expected_effect": "更快给出结论",
                    "expected_blocks": ["标题块", "正文区"],
                }
            ],
        },
        "needs_revision": True,
        "selected_element_id": "story_1",
        "last_worker_result": {
            "worker_name": "composition_worker",
            "status": "success",
            "changed_blocks": [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}],
            "assets_delta": [],
            "failure_reason": "",
        },
    }


def test_select_primary_recipe_prefers_non_noop():
    recipe = select_primary_recipe(
        {
            "action_recipes": [
                {"label": "先不处理", "scope": "noop", "prompt": ""},
                {"label": "继续优化", "scope": "priority", "prompt": "继续"},
            ]
        }
    )

    assert recipe is not None
    assert recipe["label"] == "继续优化"


def test_revision_services_build_plan_result_and_status():
    state = _base_state()

    plan = build_revision_plan(state)
    result = build_revision_result({**state, "revision_plan": plan})
    status = build_revision_status({**state, "revision_plan": plan, "revision_result": result})

    assert plan["target_block_id"] == "story_1"
    assert plan["scope"] == "selected_block"
    assert result["status"] == "success"
    assert status["status"] == "applied"


def test_artifact_patch_creates_lineage_and_knowledge_version():
    state = _base_state()
    state["artifact"] = {
        "artifact_id": "artifact_123",
        "artifact_type": "purchase_decision_note",
        "current_version_id": "version_prev",
        "current_snapshot_id": "snapshot_prev",
        "title": "Mate 60 购买决策档案",
        "status": "active",
    }
    state["artifact_version"] = {
        "version_id": "version_prev",
        "snapshot_id": "snapshot_prev",
        "revision_reason": "上一轮修改",
        "knowledge_version": "session-kb::2",
        "changed_blocks": [],
        "created_at": "2026-03-24T00:00:00",
    }
    state["revision_plan"] = build_revision_plan(state)
    state["revision_result"] = build_revision_result(state)
    patch = build_artifact_patch(state, snapshot_id="snapshot_new", checkpoint_id="ckpt_new")

    assert patch["artifact"]["artifact_id"] == "artifact_123"
    assert patch["artifact"]["current_snapshot_id"] == "snapshot_new"
    assert patch["artifact_version"]["parent_version_id"] == "version_prev"
    assert patch["artifact_version"]["snapshot_id"] == "snapshot_new"
    assert patch["artifact_version"]["checkpoint_id"] == "ckpt_new"
    assert patch["artifact_version"]["knowledge_version"] == "session-kb::3"
    assert patch["version_history_head"][0]["version_id"] == patch["artifact_version"]["version_id"]

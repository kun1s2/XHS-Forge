import pytest

from app.agents.workers.intent_worker import intent_worker
from app.services.scenario_manager import scenario_manager


def test_formal_scenario_manager_only_mounts_notes():
    assert scenario_manager.list_all_scenarios() == ["notes"]


@pytest.mark.asyncio
async def test_intent_worker_routes_asset_edit_to_retrieval_worker():
    state = {
        "active_panel": "main",
        "selected_element_id": "",
        "active_archetype": "notes",
        "main_messages": [{"content": "怎么没有图片，加一些真机图"}],
        "note_document": {
            "document_meta": {"title": "Mate 60 决策档案"},
            "blocks": [{"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"}],
        },
    }
    result = await intent_worker(state)
    decision = result["intent_decision"]
    assert result["intent_route"] == "retrieval_worker"
    assert decision["task_type"] == "edit"
    assert decision["operation_type"] == "asset_edit"
    assert decision["scope"] == "global_canvas"
    assert decision["needs_assets"] is True


@pytest.mark.asyncio
async def test_intent_worker_routes_selected_block_edits_to_composition_worker():
    state = {
        "active_panel": "content",
        "selected_element_id": "hero_1",
        "active_archetype": "notes",
        "main_messages": [{"content": "把这个结论改得更吸睛一点"}],
        "content_messages": [{"content": "把这个结论改得更吸睛一点"}],
        "note_document": {
            "document_meta": {"title": "Mate 60 决策档案"},
            "blocks": [{"id": "hero_1", "component_type": "TitleBlock", "content_brief": "结论标题"}],
        },
    }
    result = await intent_worker(state)
    assert result["intent_route"] == "composition_worker"
    assert result["agent_backends"]["intent_worker"] == "deterministic_fast_path"


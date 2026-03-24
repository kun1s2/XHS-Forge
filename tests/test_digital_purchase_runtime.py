import pytest

from app.agents.graph import route_intent
from app.agents.nodes.intent_node import intent_agent
from app.services.scenario_manager import scenario_manager


def test_formal_scenario_manager_only_mounts_seeding():
    assert scenario_manager.list_all_scenarios() == ["seeding"]


def test_route_intent_uses_new_retrieval_and_composition_nodes():
    assert route_intent({"intent_decision": {"task_type": "create"}}) == "retrieval_agent"
    assert route_intent({"intent_decision": {"task_type": "edit", "operation_type": "text_edit", "scope": "global_canvas"}}) == "composition_agent"
    assert route_intent({"intent_decision": {"task_type": "edit", "operation_type": "asset_edit", "scope": "global_canvas", "needs_assets": True}}) == "retrieval_agent"
    assert route_intent({"intent_decision": {"task_type": "review"}}) == "knowledge_review_checkpoint"


@pytest.mark.asyncio
async def test_intent_agent_existing_canvas_asset_edit_routes_to_retrieval_agent():
    state = {
        "active_panel": "main",
        "selected_element_id": "",
        "active_archetype": "seeding",
        "main_messages": [{"content": "怎么没有图片，加一些真机图"}],
        "note_document": {
            "document_meta": {"title": "Mate 60 决策档案"},
            "blocks": [{"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"}],
        },
    }
    result = await intent_agent(state)
    decision = result["intent_decision"]
    assert result["intent_route"] == "retrieval_agent"
    assert decision["task_type"] == "edit"
    assert decision["operation_type"] == "asset_edit"
    assert decision["scope"] == "global_canvas"
    assert decision["needs_assets"] is True

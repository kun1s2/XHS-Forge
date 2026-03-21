import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage

from AI_Frontend_IDE.app.agents.nodes.patch_node import surgical_patch_agent
from AI_Frontend_IDE.app.core.note_document import build_note_document


@pytest.mark.asyncio
async def test_surgical_patch_agent_uses_static_system_prompt_and_dynamic_user_message():
    state = {
        "selected_element_id": "title_1",
        "main_messages": [HumanMessage(content="把标题改得更克制一点")],
        "note_document": build_note_document(
            document_view={
                "page_title": "旧标题页",
                "blocks": [{"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"}],
                "title_1": {"type": "TitleBlock", "title": "旧标题"},
            },
            block_style_map={},
        ),
    }

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [type("Msg", (), {"content": "修改完成"})()],
        "note_document": build_note_document(
            document_view={
                "page_title": "旧标题页",
                "blocks": [{"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"}],
                "title_1": {"type": "TitleBlock", "title": "新标题"},
            },
            block_style_map={},
        ),
    }

    captured = {}

    def fake_create_controlled_agent(**kwargs):
        captured.update(kwargs)
        return mock_agent

    with patch("AI_Frontend_IDE.app.agents.nodes.patch_node.create_controlled_agent", side_effect=fake_create_controlled_agent):
        result = await surgical_patch_agent(state)

    title_block = next(block for block in result["note_document"]["blocks"] if block["id"] == "title_1")
    assert title_block["props"]["title"] == "新标题"
    assert captured["name"] == "patch_doctor"
    assert "资深的前端微调专家" in captured["prompt"]
    args, _ = mock_agent.ainvoke.call_args
    user_message = args[0]["messages"][0][1]
    assert "title_1" in user_message
    assert "更克制一点" in user_message

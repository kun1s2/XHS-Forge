import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch
from AI_Frontend_IDE.app.agents.nodes.enrichment_agent import enrichment_node_v2
from AI_Frontend_IDE.app.agents.state import UIProjectState
from AI_Frontend_IDE.app.core.note_document import build_note_document

@pytest.mark.asyncio
async def test_enrichment_node_v2_basic():
    """测试 enrichment_node_v2 的基本逻辑，模拟工具调用返回。"""
    
    # 1. 准备初始状态
    initial_state: UIProjectState = {
        "note_document": build_note_document(
            document_view={
                "page_title": "测试页面",
                "blocks": [
                    {"id": "comp_1", "component_type": "ProductSpecCard", "content_brief": "待增强商品"},
                ],
                "comp_1": {"type": "ProductSpecCard", "title": "待增强商品"},
            },
            block_style_map={},
        ),
        "active_archetype": "electronics",
        "image_assets": []
    }

    # 2. 模拟 enrichment_react_agent 的 ainvoke 返回
    # 我们模拟 Agent 调用了 enrich_product_tool 并返回了增强后的 DSL
    mock_enriched_result = {
        "source": "product",
        "note_document": build_note_document(
            document_view={
                "page_title": "测试页面",
                "blocks": [
                    {"id": "comp_1", "component_type": "ProductSpecCard", "content_brief": "待增强商品"},
                ],
                "comp_1": {"type": "ProductSpecCard", "title": "增强后的索尼相机", "price": "5999"},
            },
            block_style_map={},
        ),
    }
    
    mock_result = {
        "messages": [
            AsyncMock(
                type="tool", 
                content=json.dumps(mock_enriched_result)
            )
        ]
    }

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = mock_result
    captured = {}

    def fake_create_controlled_agent(**kwargs):
        captured.update(kwargs)
        return mock_agent

    with patch("AI_Frontend_IDE.app.agents.nodes.enrichment_agent.create_controlled_agent", side_effect=fake_create_controlled_agent):
        result = await enrichment_node_v2(initial_state)

    block = next(block for block in result["note_document"]["blocks"] if block["id"] == "comp_1")
    assert block["props"]["title"] == "增强后的索尼相机"
    assert block["props"]["price"] == "5999"
    assert [item["id"] for item in result["note_document"]["blocks"]] == [item["id"] for item in initial_state["note_document"]["blocks"]]
    assert captured["name"] == "enrichment_agent"
    assert "高级数据增强管家" in captured["prompt"]

    args, kwargs = mock_agent.ainvoke.call_args
    prompt_sent = args[0]["messages"][0][1]
    assert "electronics" in prompt_sent

@pytest.mark.asyncio
async def test_enrichment_node_v2_empty_dsl():
    """测试当 note_document 为空时，节点应直接返回空字典。"""
    state = {"note_document": {"document_meta": {"title": "空页"}, "blocks": [], "assets": []}, "active_archetype": "general"}
    result = await enrichment_node_v2(state)
    assert result == {}

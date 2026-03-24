# 🧪 战役三：自主管家与无损合并 (Enrichment Tool Calling Tests)
import pytest
import json
from unittest.mock import AsyncMock, patch
from langchain_core.messages import AIMessage, ToolMessage
from AI_Frontend_IDE.app.agents.nodes.enrichment_agent import enrichment_node
from AI_Frontend_IDE.app.agents.state import UIProjectState
from AI_Frontend_IDE.app.core.note_document import build_note_document

@pytest.mark.asyncio
async def test_enrichment_empty_run_no_tools():
    """按需决策空跑：仅纯文本组件时，应零次调用 Tool（通过 Mock 验证 ainvoke 仅被调用 1 次且无 tool 消息）。"""
    state: UIProjectState = {
        "note_document": build_note_document(
            document_view={
                "page_title": "纯文本页面",
                "blocks": [
                    {"id": "text_1", "component_type": "StoryText", "content_brief": "正文"},
                    {"id": "text_2", "component_type": "TitleBlock", "content_brief": "标题"},
                ],
                "text_1": {"type": "StoryText", "paragraphs": ["纯文本内容"]},
                "text_2": {"type": "TitleBlock", "title": "标题"},
            },
            block_style_map={},
        ),
        "active_archetype": "general",
        "image_assets": [],
    }

    # 使用 LangChain 原生消息载体，保证 Mock 与生产环境 100% 数据契合
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [AIMessage(content="当前页面仅有纯文本组件，无需增强。")],
    }

    with patch("AI_Frontend_IDE.app.agents.nodes.enrichment_agent.create_controlled_agent", return_value=mock_agent):
        result = await enrichment_node(state)

    assert result["note_document"] == state["note_document"]
    assert result["image_assets"] == []
    # Agent 只被调用一次（一次 ainvoke）
    assert mock_agent.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_enrichment_parallel_tools_and_safe_merge():
    """并行工具与深度合并：同时存在缺图 ProductCard 与缺坐标 LocationBlock，合并后原有文本/价格不丢失。"""
    original_document_view = {
        "page_title": "增强页",
        "blocks": [
            {"id": "product_1", "component_type": "ProductSpecCard", "content_brief": "商品参数"},
            {"id": "location_1", "component_type": "LocationBlock", "content_brief": "地点"},
            {"id": "text_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "product_1": {"type": "ProductSpecCard", "title": "富士 X100VI", "price": "¥12999", "image_url": ""},
        "location_1": {"type": "LocationBlock", "address": "上海外滩", "lat": None, "lng": None},
        "text_1": {"type": "StoryText", "paragraphs": ["这是一段不能被覆盖的正文"]},
    }
    state: UIProjectState = {
        "note_document": build_note_document(
            document_view=original_document_view,
            block_style_map={},
        ),
        "active_archetype": "seeding",
        "image_assets": [],
    }

    # 模拟两次 tool 返回：一次图片增强，一次位置增强（使用 LangChain 原生 ToolMessage 保真还原）
    tool_results = [
        {
            "source": "images",
            "note_document": build_note_document(
                document_view={
                    **original_document_view,
                    "product_1": {**original_document_view["product_1"], "image_url": "https://gen/image.jpg"},
                },
                block_style_map={},
            ),
            "new_assets": [{"url": "https://gen/image.jpg"}],
        },
        {
            "source": "location",
            "note_document": build_note_document(
                document_view={
                    **original_document_view,
                    "location_1": {**original_document_view["location_1"], "lat": 31.23, "lng": 121.49},
                },
                block_style_map={},
            ),
        },
    ]

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            ToolMessage(
                content=json.dumps(tool_results[0], ensure_ascii=False),
                tool_call_id="call_1",
                name="generate_images_tool",
            ),
            ToolMessage(
                content=json.dumps(tool_results[1], ensure_ascii=False),
                tool_call_id="call_2",
                name="enrich_location_tool",
            ),
        ]
    }

    with patch("AI_Frontend_IDE.app.agents.nodes.enrichment_agent.create_controlled_agent", return_value=mock_agent):
        result = await enrichment_node(state)

    final = result["note_document"]
    product = next(block for block in final["blocks"] if block["id"] == "product_1")
    location = next(block for block in final["blocks"] if block["id"] == "location_1")
    story = next(block for block in final["blocks"] if block["id"] == "text_1")
    assert product["props"]["title"] == "富士 X100VI"
    assert product["props"]["price"] == "¥12999"
    assert product["props"]["image_url"] == "https://gen/image.jpg"
    assert location["props"]["lat"] == 31.23
    assert location["props"]["lng"] == 121.49
    assert story["props"]["paragraphs"] == ["这是一段不能被覆盖的正文"]
    assert len(result["image_assets"]) == 1

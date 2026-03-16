# 🧪 战役三：自主管家与无损合并 (Enrichment Tool Calling Tests)
import pytest
import json
from unittest.mock import AsyncMock, patch
from langchain_core.messages import AIMessage, ToolMessage
from AI_Frontend_IDE.app.agents.nodes.enrichment_agent import enrichment_node_v2
from AI_Frontend_IDE.app.agents.state import UIProjectState

@pytest.mark.asyncio
async def test_enrichment_empty_run_no_tools():
    """按需决策空跑：仅纯文本组件时，应零次调用 Tool（通过 Mock 验证 ainvoke 仅被调用 1 次且无 tool 消息）。"""
    state: UIProjectState = {
        "data_dsl": {
            "text_1": {"type": "StoryText", "paragraphs": ["纯文本内容"]},
            "text_2": {"type": "TitleBlock", "title": "标题"},
        },
        "active_archetype": "general",
        "image_assets": [],
    }

    # 使用 LangChain 原生消息载体，保证 Mock 与生产环境 100% 数据契合
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [AIMessage(content="当前页面仅有纯文本组件，无需增强。")],
    }

    with patch("AI_Frontend_IDE.app.agents.nodes.enrichment_agent.create_react_agent", return_value=mock_agent):
        result = await enrichment_node_v2(state)

    # 无 tool 消息，final_data_dsl 应保持原样
    assert result["data_dsl"] == state["data_dsl"]
    assert result["image_assets"] == []
    # Agent 只被调用一次（一次 ainvoke）
    assert mock_agent.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_enrichment_parallel_tools_and_safe_merge():
    """并行工具与深度合并：同时存在缺图 ProductCard 与缺坐标 LocationBlock，合并后原有文本/价格不丢失。"""
    original_dsl = {
        "product_1": {"type": "ProductCard", "title": "富士 X100VI", "price": "¥12999", "image_url": ""},
        "location_1": {"type": "LocationBlock", "address": "上海外滩", "lat": None, "lng": None},
        "text_1": {"type": "StoryText", "paragraphs": ["这是一段不能被覆盖的正文"]},
    }
    state: UIProjectState = {
        "data_dsl": original_dsl,
        "active_archetype": "seeding",
        "image_assets": [],
    }

    # 模拟两次 tool 返回：一次图片增强，一次位置增强（使用 LangChain 原生 ToolMessage 保真还原）
    tool_results = [
        {"source": "images", "data_dsl": {"product_1": {"image_url": "https://gen/image.jpg"}}, "new_assets": [{"url": "https://gen/image.jpg"}]},
        {"source": "location", "data_dsl": {"location_1": {"lat": 31.23, "lng": 121.49}}},
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

    with patch("AI_Frontend_IDE.app.agents.nodes.enrichment_agent.create_react_agent", return_value=mock_agent):
        result = await enrichment_node_v2(state)

    final = result["data_dsl"]
    # 致命校验：原有信息不丢失
    assert final["product_1"]["title"] == "富士 X100VI"
    assert final["product_1"]["price"] == "¥12999"
    assert final["product_1"]["image_url"] == "https://gen/image.jpg"
    assert final["location_1"]["lat"] == 31.23
    assert final["location_1"]["lng"] == 121.49
    assert final["text_1"]["paragraphs"] == ["这是一段不能被覆盖的正文"]
    assert len(result["image_assets"]) == 1

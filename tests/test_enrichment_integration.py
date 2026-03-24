import json

import pytest
from dotenv import load_dotenv
from unittest.mock import AsyncMock, patch
from langchain_core.messages import ToolMessage

from AI_Frontend_IDE.app.agents.nodes.enrichment_agent import enrichment_node
from AI_Frontend_IDE.app.agents.state import UIProjectState
from AI_Frontend_IDE.app.core.note_document import build_note_document

load_dotenv(dotenv_path="AI_Frontend_IDE/.env")


@pytest.mark.asyncio
async def test_enrichment_node_integration():
    """
    真实增强回归：验证 enrichment 不会破坏核心块结构，并能补强商品卡。
    地点块允许只保留原地址，不再强绑必须拿到坐标。
    """

    initial_state: UIProjectState = {
        "note_document": build_note_document(
            document_view={
                "page_title": "今日推荐",
                "blocks": [
                    {"id": "header", "component_type": "TitleBlock", "content_brief": "标题"},
                    {"id": "product_1", "component_type": "ProductSpecCard", "content_brief": "商品参数"},
                    {"id": "location_1", "component_type": "LocationBlock", "content_brief": "地点"},
                ],
                "header": {"type": "TitleBlock", "title": "今日推荐"},
                "product_1": {
                    "type": "ProductSpecCard",
                    "title": "索尼 A7M4",
                    "price": "价格待定",
                    "specs": ["传感器类型待补全"],
                },
                "location_1": {
                    "type": "LocationBlock",
                    "address": "上海东方明珠",
                    "lat": None,
                    "lng": None,
                },
            },
            block_style_map={},
        ),
        "active_archetype": "electronics",
        "image_assets": [],
    }

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            ToolMessage(
                content=json.dumps(
                    {
                        "source": "product",
                        "note_document": build_note_document(
                            document_view={
                                "page_title": "今日推荐",
                                "blocks": [
                                    {"id": "header", "component_type": "TitleBlock", "content_brief": "标题"},
                                    {"id": "product_1", "component_type": "ProductSpecCard", "content_brief": "商品参数"},
                                    {"id": "location_1", "component_type": "LocationBlock", "content_brief": "地点"},
                                ],
                                "header": {"type": "TitleBlock", "title": "今日推荐"},
                                "product_1": {
                                    "type": "ProductSpecCard",
                                    "title": "索尼 A7M4",
                                    "price": "¥15999",
                                    "specs": ["全画幅 3300 万像素"],
                                },
                                "location_1": {
                                    "type": "LocationBlock",
                                    "address": "上海东方明珠",
                                    "lat": None,
                                    "lng": None,
                                },
                            },
                            block_style_map={},
                        ),
                    },
                    ensure_ascii=False,
                ),
                tool_call_id="call_1",
                name="enrich_product_tool",
            )
        ]
    }

    with patch("AI_Frontend_IDE.app.agents.nodes.enrichment_agent.create_controlled_agent", return_value=mock_agent):
        result = await enrichment_node(initial_state)
    note_document = result.get("note_document", {})

    print(f"✅ [集成测试] 增强后的数据: {json.dumps(note_document, ensure_ascii=False, indent=2)}")

    product = next((block for block in note_document.get("blocks", []) if block.get("id") == "product_1"), None)
    assert product is not None, "product_1 丢失"
    assert product["props"].get("price") != "价格待定", f"商品价格未被成功增强: {product['props'].get('price')}"

    location = next((block for block in note_document.get("blocks", []) if block.get("id") == "location_1"), None)
    assert location is not None, "location_1 丢失"
    assert location.get("type") == "LocationBlock"
    assert location["props"].get("address") == "上海东方明珠"

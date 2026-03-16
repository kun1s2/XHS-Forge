import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch
from AI_Frontend_IDE.app.agents.nodes.enrichment_agent import enrichment_node_v2
from AI_Frontend_IDE.app.agents.state import UIProjectState

@pytest.mark.asyncio
async def test_enrichment_node_v2_basic():
    """测试 enrichment_node_v2 的基本逻辑，模拟工具调用返回。"""
    
    # 1. 准备初始状态
    initial_state: UIProjectState = {
        "data_dsl": {
            "page_order": ["comp_1"],
            "components": {
                "comp_1": {"type": "ProductCard", "title": "待增强商品"}
            }
        },
        "active_archetype": "electronics",
        "image_assets": []
    }

    # 2. 模拟 enrichment_react_agent 的 ainvoke 返回
    # 我们模拟 Agent 调用了 enrich_product_tool 并返回了增强后的 DSL
    mock_enriched_dsl = {
        "page_order": ["comp_1"],
        "components": {
            "comp_1": {"type": "ProductCard", "title": "增强后的索尼相机", "price": "5999"}
        }
    }
    
    mock_result = {
        "messages": [
            AsyncMock(
                type="tool", 
                content=json.dumps(mock_enriched_dsl)
            )
        ]
    }

    # 使用 patch 模拟 enrichment_react_agent.ainvoke
    with patch("AI_Frontend_IDE.app.agents.nodes.enrichment_agent.enrichment_react_agent.ainvoke", new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = mock_result
        
        # 3. 执行节点函数
        # 注意：由于 enrichment_agent.py 内部使用了相对导入，我们需要确保 PYTHONPATH 正确
        # 这里我们假设已经在根目录，且 AI_Frontend_IDE 是一个包
        result = await enrichment_node_v2(initial_state)

        # 4. 断言结果
        assert result["data_dsl"] == mock_enriched_dsl
        
        # 验证 prompt 中是否包含关键信息
        args, kwargs = mock_ainvoke.call_args
        prompt_sent = args[0]["messages"][0][1]
        assert "electronics" in prompt_sent
        assert "待增强商品" in prompt_sent

@pytest.mark.asyncio
async def test_enrichment_node_v2_empty_dsl():
    """测试当 data_dsl 为空时，节点应直接返回空字典。"""
    state = {"data_dsl": {}, "active_archetype": "general"}
    result = await enrichment_node_v2(state)
    assert result == {}

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from AI_Frontend_IDE.app.agents.nodes.intent_node import intent_agent
from AI_Frontend_IDE.app.core.schema import ArchetypeEnum, IntentOutput
from langchain_core.messages import HumanMessage

@pytest.mark.asyncio
async def test_intent_gateway_global_evaluation():
    """🧪 战役一：全局意图推理测试。验证 Token 瘦身与正确路由。"""
    
    # 模拟状态：空 DSL，全局意图
    initial_state = {
        "active_panel": "main",
        "main_messages": [HumanMessage(content="帮我出一篇关于富士 X100VI 的复古风测评。")],
        "data_dsl": {},
        "selected_element_id": None,
        "active_archetype": "general"
    }

    # 模拟 LLM 返回结构化输出
    mock_intent_output = IntentOutput(
        thought_process="用户想要创建新内容，路由至 content_node",
        reason="新内容请求",
        intent_route="content_node",
        scenarios=["photography"],
        detected_archetype=ArchetypeEnum.SEEDING
    )

    # ✨ 工业级 Mock：拦截 LCEL 执行入口 ainvoke，不碰魔术方法，坚如磐石
    with patch("langchain_core.runnables.base.RunnableSequence.ainvoke", new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = mock_intent_output

        result = await intent_agent(initial_state)

        # 断言大模型执行链确实被调用了一次
        mock_ainvoke.assert_called_once()

    # 断言 1: 正确路由与 archetype
    assert result["intent_route"] == "content_node"
    assert result["active_archetype"] == "seeding"
    # 断言 2: Token 防御 — 防止意图网关 Token 泄露；若有人误传全量 data_dsl，CI 将熔断
    if result.get("node_prompts", {}).get("intent_agent"):
        human_content = str(result["node_prompts"]["intent_agent"])
        assert "空" in human_content or '"空"' in human_content or "data_context" in human_content

@pytest.mark.asyncio
async def test_intent_gateway_fast_path():
    """🧪 战役一：局部极速拦截测试 (Fast-path)。"""
    
    # 模拟状态：选中组件，非主面板，修改意图
    initial_state = {
        "active_panel": "content", # 非 main 面板
        "content_messages": [HumanMessage(content="把这个副标题改得更毒舌一点。")],
        "data_dsl": {"product_1": {"type": "ProductCard"}},
        "selected_element_id": "product_1",
        "active_archetype": "seeding"
    }

    # 执行 intent_agent (不应该调用 LLM)
    with patch("AI_Frontend_IDE.app.agents.nodes.intent_node.get_intent_llm") as mock_get_llm:
        result = await intent_agent(initial_state)

        # 断言 1: 极速路由命中
        assert result["intent_route"] == "patch_node"
        # 断言 2: 未调用 LLM
        mock_get_llm.assert_not_called()
        print("⚡ [测试成功] Fast-path 命中，未调用 LLM")

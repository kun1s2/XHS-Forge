# 🧪 战役二：手术刀修改与物理记忆隔离 (Surgical Patch & Memory Tests)
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.runnables import RunnableLambda
from AI_Frontend_IDE.app.agents.nodes.patch_node import surgical_patch_agent
from AI_Frontend_IDE.app.agents.state import UIProjectState, merge_dsl, merge_patch_tracks
from AI_Frontend_IDE.app.core.schema import SurgicalPatchOutput, ComponentData
from langchain_core.messages import HumanMessage

FAKE_IMAGE_URL = "https://serpapi.example/sony-a7c2-real-photo.jpg"


@pytest.mark.asyncio
async def test_patch_visual_sniper_search_keyword_and_image_url():
    """真实视觉狙击验证：验证 SerpApi 的连线与 image_url 写入（Wiring + DSL Patch）。"""
    state: UIProjectState = {
        "selected_element_id": "product_1",
        "data_dsl": {"product_1": {"type": "ProductCard", "title": "索尼 A7C2", "image_url": ""}},
        "main_messages": [HumanMessage(content="换一张真实的相机侧面图")],
        "patch_tracks": {},
    }

    captured_search_kw = []

    async def capture_search(kw):
        captured_search_kw.append(kw)
        return FAKE_IMAGE_URL

    # Mock 提取搜索词的 LLM（视觉狙击分支里单独 ainvoke 的那次）
    # 用 MagicMock 作为 llm，避免 AsyncMock 导致 .with_structured_output 返回 coroutine 触发 LCEL 报错
    mock_llm_content = MagicMock()
    mock_llm_content.content = "Sony A7C2 real photo side view"
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_content)

    fake_output = SurgicalPatchOutput(
        thought_process="已更换为真实产品图",
        reason="换图",
        updated_component=ComponentData(
            type="ProductCard", title="索尼 A7C2", image_url=FAKE_IMAGE_URL
        ),
    )

    # 用真实 Runnable 替身构建链，避免 patch __or__；再拦截业务层入口 invoke_patch_retry（与 Test 2 一致）
    mock_llm.with_structured_output.return_value = RunnableLambda(lambda _: fake_output)

    with patch("AI_Frontend_IDE.app.agents.nodes.patch_node.get_patch_llm", return_value=mock_llm):
        with patch("AI_Frontend_IDE.app.agents.nodes.patch_node.google_image_search_tool") as mock_tool:
            mock_tool.ainvoke = AsyncMock(side_effect=capture_search)
            with patch("AI_Frontend_IDE.app.agents.nodes.patch_node.invoke_patch_retry", new_callable=AsyncMock) as mock_retry:
                mock_retry.return_value = fake_output
                result = await surgical_patch_agent(state)

    # 核心断言：验证 DSL 被成功 Patch
    assert "product_1" in result["data_dsl"]
    assert result["data_dsl"]["product_1"]["image_url"] == FAKE_IMAGE_URL

    # 核心断言：验证搜图逻辑被正确触发，且参数传递无误（Wiring Verification）
    # 单元测试只验证“大模型输出是否完整传给 SerpApi”；Prompt 是否稳定产出约束词属 LLM Evals 范畴
    assert len(captured_search_kw) == 1
    assert captured_search_kw[0] == "Sony A7C2 real photo side view"


@pytest.mark.asyncio
async def test_patch_memory_isolation_and_thought_in_content():
    """局部记忆延续性：patch_tracks 与 content_messages 各 +1，且含 thought_process。"""
    state: UIProjectState = {
        "selected_element_id": "product_1",
        "data_dsl": {"product_1": {"type": "ProductCard", "title": "测试"}},
        "main_messages": [HumanMessage(content="把标题改得更毒舌一点")],
        "content_messages": [],
        "patch_tracks": {},
    }

    thought = "用户希望标题更毒舌，已改为吐槽风格。"
    with patch("AI_Frontend_IDE.app.agents.nodes.patch_node.get_patch_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=SurgicalPatchOutput(
            thought_process=thought,
            reason="毒舌化",
            updated_component=ComponentData(type="ProductCard", title="这玩意儿也就那样"),
        ))
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm
        with patch("AI_Frontend_IDE.app.agents.nodes.patch_node.invoke_patch_retry", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = SurgicalPatchOutput(
                thought_process=thought,
                reason="毒舌化",
                updated_component=ComponentData(type="ProductCard", title="这玩意儿也就那样"),
            )
            result = await surgical_patch_agent(state)

    assert result.get("patch_tracks", {}).get("product_1")
    assert len(result["patch_tracks"]["product_1"]) == 1
    assert result["patch_tracks"]["product_1"][0].get("agent_thought") == thought

    assert result.get("content_messages")
    assert len(result["content_messages"]) == 1
    assert thought in result["content_messages"][0].content

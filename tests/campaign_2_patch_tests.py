# 🧪 战役二：手术刀修改与物理记忆隔离 (Surgical Patch & Memory Tests)
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from AI_Frontend_IDE.app.agents.nodes.patch_node import surgical_patch_agent
from AI_Frontend_IDE.app.agents.state import UIProjectState
from AI_Frontend_IDE.app.core.note_document import build_note_document

FAKE_IMAGE_URL = "https://serpapi.example/sony-a7c2-real-photo.jpg"


def test_patch_agent_surfaces_execution_patch_and_success_message():
    """补丁节点应把子 agent 的执行补丁和确认消息返回给主链。"""
    state: UIProjectState = {
        "selected_element_id": "product_1",
        "note_document": build_note_document(
            document_view={
                "blocks": [{"id": "product_1", "component_type": "ProductCard", "content_brief": ""}],
                "product_1": {"type": "ProductCard", "title": "索尼 A7C2", "image_url": ""},
            },
            block_style_map={},
        ),
        "main_messages": [HumanMessage(content="换一张真实的相机侧面图")],
        "patch_tracks": {},
    }

    fake_patch_doctor = MagicMock()
    fake_patch_doctor.backend = "create_agent"
    fake_patch_doctor.ainvoke = AsyncMock(
        return_value={
            "messages": [AIMessage(content="图片已替换完成")],
            "note_document": build_note_document(
                document_view={
                    "blocks": [{"id": "product_1", "component_type": "ProductCard", "content_brief": ""}],
                    "product_1": {"type": "ProductCard", "title": "索尼 A7C2", "image_url": FAKE_IMAGE_URL},
                },
                block_style_map={},
            ),
        }
    )

    async def _run():
        with patch("AI_Frontend_IDE.app.agents.nodes.patch_node.create_controlled_agent", return_value=fake_patch_doctor):
            return await surgical_patch_agent(state)

    result = asyncio.run(_run())

    assert result["note_document"]["blocks"][0]["id"] == "product_1"
    assert result["note_document"]["blocks"][0]["props"]["image_url"] == FAKE_IMAGE_URL
    assert result["agent_backends"]["patch_doctor"] == "create_agent"
    assert "图片已替换完成" in result["main_messages"][0].content


def test_patch_agent_returns_skip_when_no_selection():
    """未选中组件时，补丁节点应直接跳过并返回清晰提示。"""
    state: UIProjectState = {
        "selected_element_id": None,
        "patch_tracks": {},
    }

    result = asyncio.run(surgical_patch_agent(state))

    assert result["agent_backends"]["patch_doctor"] == "skipped_no_selection"
    assert "未选中任何组件" in result["main_messages"][0].content
